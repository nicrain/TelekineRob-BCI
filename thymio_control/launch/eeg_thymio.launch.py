from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    core = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [PathJoinSubstitution([get_package_share_directory("thymio_control"), "launch", "experiment_core.launch.py"])]
        ),
        launch_arguments={
            "run_eeg": "true",
            "use_teleop": "false",
        }.items(),
    )
    return LaunchDescription([core])
