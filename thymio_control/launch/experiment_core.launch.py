import os

import yaml
from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import AnyLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node


def _str(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    return str(v).lower()


def _load_defaults():
    try:
        cfg_path = os.path.join(get_package_share_directory("thymio_control"), "config", "launch_args.yaml")
        with open(cfg_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def generate_launch_description():
    defaults = _load_defaults()
    gz_partition = f"thymio_{os.getpid()}"

    use_sim = LaunchConfiguration("use_sim")
    use_gui = LaunchConfiguration("use_gui")
    use_teleop = LaunchConfiguration("use_teleop")
    run_eeg = LaunchConfiguration("run_eeg")
    run_rviz = LaunchConfiguration("run_rviz")
    eeg_config_file = LaunchConfiguration("eeg_config_file")
    eeg_input = LaunchConfiguration("input")
    role = LaunchConfiguration("role")
    device = LaunchConfiguration("device")

    decls = [
        DeclareLaunchArgument("use_sim", default_value=_str(defaults.get("use_sim", False))),
        DeclareLaunchArgument("use_gui", default_value=_str(defaults.get("use_gui", True))),
        DeclareLaunchArgument("use_teleop", default_value=_str(defaults.get("use_teleop", False))),
        DeclareLaunchArgument("run_eeg", default_value=_str(defaults.get("run_eeg", True))),
        DeclareLaunchArgument("run_rviz", default_value=_str(defaults.get("run_rviz", False))),
        DeclareLaunchArgument(
            "eeg_config_file",
            default_value=os.path.join(
                get_package_share_directory("thymio_control"),
                "config",
                defaults.get("eeg_config_file", "eeg_control_node.params.yaml"),
            ),
        ),
        DeclareLaunchArgument("input", default_value="lsl"),
        DeclareLaunchArgument("role", default_value="speed"),
        DeclareLaunchArgument("device", default_value=""),
    ]

    cmd_topic = PythonExpression(["'/model/thymio/cmd_vel' if '", use_sim, "' == 'true' else '/cmd_vel'"])

    set_gz_resource_path = SetEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=[
            os.path.join(get_package_share_directory("thymio_control"), "config"),
            ":",
            os.path.join(get_package_share_directory("thymio_description"), "urdf"),
        ],
    )

    gz_sim_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [PathJoinSubstitution([get_package_share_directory("ros_gz_sim"), "launch", "gz_sim.launch.py"])]
        ),
        launch_arguments={"gz_args": ["-r ", "thymio_world.sdf"]}.items(),
        condition=IfCondition(PythonExpression(["'", use_sim, "' == 'true' and '", use_gui, "' == 'true'"])),
    )
    gz_sim_headless = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [PathJoinSubstitution([get_package_share_directory("ros_gz_sim"), "launch", "gz_sim.launch.py"])]
        ),
        launch_arguments={"gz_args": ["-r -s ", "thymio_world.sdf"]}.items(),
        condition=IfCondition(PythonExpression(["'", use_sim, "' == 'true' and '", use_gui, "' == 'false'"])),
    )

    gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        parameters=[{"config_file": os.path.join(get_package_share_directory("thymio_control"), "config", "gz_bridge.yaml")}],
        output="log",
        condition=IfCondition(use_sim),
    )

    sim_model_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [PathJoinSubstitution([get_package_share_directory("thymio_description"), "launch", "model.launch.py"])]
        ),
        launch_arguments={"name": "", "namespace": "", "use_sim_time": "true"}.items(),
        condition=IfCondition(use_sim),
    )

    sim_spawn_thymio = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=["-name", "thymio", "-topic", "robot_description", "-x", "0.0", "-y", "0.0", "-z", "0.08"],
        output="log",
        condition=IfCondition(use_sim),
    )

    try:
        real_robot_driver = IncludeLaunchDescription(
            AnyLaunchDescriptionSource(
                [PathJoinSubstitution([get_package_share_directory("thymio_driver"), "launch", "main.launch"])]
            ),
            launch_arguments={"device": device}.items(),
            condition=UnlessCondition(use_sim),
        )
    except PackageNotFoundError:
        real_robot_driver = LogInfo(msg="Skip: thymio_driver package not found.")

    eeg_node = Node(
        package="thymio_control",
        executable="eeg_control_node.py",
        parameters=[eeg_config_file, {"cmd_topic": cmd_topic, "input": eeg_input, "role": role}],
        output="log",
        condition=IfCondition(PythonExpression(["'", run_eeg, "' == 'true' and '", use_teleop, "' == 'false'"])),
    )

    teleop_node = Node(
        package="teleop_twist_keyboard",
        executable="teleop_twist_keyboard",
        name="teleop",
        remappings=[("cmd_vel", cmd_topic)],
        output="log",
        condition=IfCondition(use_teleop),
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        arguments=["-d", os.path.join(get_package_share_directory("thymio_control"), "config", "default.rviz"), "--ros-args", "--log-level", "error"],
        parameters=[{"use_sim_time": True}],
        output="log",
        condition=IfCondition(run_rviz),
    )

    return LaunchDescription(
        decls
        + [
            set_gz_resource_path,
            SetEnvironmentVariable("GZ_PARTITION", gz_partition),
            LogInfo(msg=["GZ_PARTITION=", gz_partition]),
            LogInfo(msg=["Launch: sim=", use_sim, " eeg=", run_eeg, " teleop=", use_teleop, " rviz=", run_rviz]),
            gz_sim_gui,
            gz_sim_headless,
            sim_model_publisher,
            sim_spawn_thymio,
            gz_bridge,
            real_robot_driver,
            eeg_node,
            teleop_node,
            rviz_node,
        ]
    )
