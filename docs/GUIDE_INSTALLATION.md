# GUIDE_INSTALLATION

> 安装指南 — 骨架(待后续单填充正文)。规矩:中文叙述只翻技术标识符之外的部分;内部三方注解(CTO/programmer/reviewer)禁止入正文。术语与 docs/GLOSSAIRE.md 保持一致。

## 1. 概览与前置要求

> 写什么:系统架构一段话 + 硬软件清单(Windows + WSL2 + ROS2 + Thymio + Aseba)。

## 2. Windows 主机准备(g.tec 驱动 + bridge)

> 写什么:安装 g.Pype / UnicornPy 驱动、bridge 脚本、授权闸门(open_in_ide)说明。

## 3. WSL2 环境(Ubuntu 24.04、ROS2 Kilted、systemd)

> 写什么:WSL2 装 Ubuntu 24.04、ROS2 Kilted、启用 systemd、colcon build。

## 4. 网络配置(IPv6 禁用、LAN 端口转发)

> 写什么:禁用 eth0 IPv6(强制 LSL 走 IPv4)、NAT + netsh portproxy 5173、UAC 修复按钮。

## 5. Web GUI 安装

> 写什么:后端 FastAPI(venv)+ 前端 vite 构建步骤与环境变量表。

## 6. 真机验证清单

> 写什么:安装后逐项验收(设备连上、波形、校准、实验导出)。

## 7. 依赖与版本表

> 写什么:关键依赖与版本(Python / ROS2 / numpy / scipy / pylsl 等)。
