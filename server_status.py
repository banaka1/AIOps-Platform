"""
实时服务器状态工具
- 基于 psutil 采集本机 CPU / 内存 / 磁盘 / 主机名 / IP / 操作系统 等实时指标
- GPU 指标分层采集（显卡型号 / 利用率 / 显存 / 温度）：
  1. NVIDIA：pynvml，精确采集利用率、显存、温度（需 NVIDIA 驱动，pip install pynvml）
  2. AMD/Intel/其他（Windows）：Win32_VideoController 拿型号 + 注册表拿真实显存总量
     + GPU Engine / GPU Adapter Memory 性能计数器拿利用率与显存占用（系统自带，无需额外依赖）
  3. AMD：pyadl 尽力补充温度/利用率（部分驱动不支持，失败则静默跳过，pip install pyadl）
- 替代 ops.db 中的模拟数据，前端询问"当前/实时"服务器状态时返回真实设备数据
"""
import os
import json
import base64
import socket
import platform
import subprocess
from typing import Optional

import psutil
from langchain_core.tools import tool

from tool_registry import registry


def _local_ip() -> str:
    """获取本机局域网 IP，失败回退到 gethostbyname"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def _disk_path() -> str:
    """跨平台系统盘路径：Windows 取 SystemDrive，类 Unix 取 /"""
    if os.name == "nt":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


# ---------------- GPU 采集：NVIDIA（pynvml） ----------------
def _gpu_nvidia() -> list:
    """pynvml 采集 NVIDIA 显卡；未安装库或无 N 卡时返回空列表"""
    try:
        import pynvml
        pynvml.nvmlInit()
    except Exception:
        return []
    try:
        result = []
        for i in range(pynvml.nvmlDeviceGetCount()):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                name = name.decode(errors="replace")
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            try:
                temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                temp = None
            result.append({
                "name": name,
                "util": util.gpu,
                "mem_used_bytes": mem.used,
                "mem_total_bytes": mem.total,
                "temp": temp,
            })
        return result
    except Exception:
        return []
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass


# ---------------- GPU 采集：AMD（pyadl，尽力补充） ----------------
def _gpu_amd() -> dict:
    """pyadl 采集 AMD 显卡温度/利用率；驱动不支持时对应字段为 None，库不可用返回空 dict"""
    try:
        import pyadl
        devs = pyadl.ADLManager.getInstance().getDevices()
    except Exception:
        return {}
    result = {}
    for d in devs:
        name = getattr(d, "adapterName", None)
        if isinstance(name, bytes):
            name = name.decode(errors="replace")
        if not name:
            continue
        item = {"util": None, "temp": None}
        try:
            item["util"] = d.getCurrentUsage()
        except Exception:
            pass
        try:
            item["temp"] = d.getCurrentTemperature()
        except Exception:
            pass
        result[name] = item
    return result


# ---------------- GPU 采集：Windows 性能计数器（全品牌兜底） ----------------
_PS_GPU_SCRIPT = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ErrorActionPreference = 'SilentlyContinue'
$result = [ordered]@{ gpus = @(); utilPercent = $null; vramUsedBytes = $null }

# 注册表拿真实显存总量（CIM 的 AdapterRAM 是 uint32，大显存会被截断成 ~4GB）
$regTotals = @{}
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}' |
  ForEach-Object {
    $p = Get-ItemProperty -Path $_.PSPath
    if ($p.DriverDesc -and $p.'HardwareInformation.qwMemorySize') {
      $regTotals[$p.DriverDesc] = [uint64]$p.'HardwareInformation.qwMemorySize'
    }
  }

# 显卡列表以 CIM 为准（注册表可能残留旧驱动条目）
Get-CimInstance Win32_VideoController | ForEach-Object {
  $total = [uint64]0
  if ($regTotals.ContainsKey($_.Name)) { $total = $regTotals[$_.Name] }
  elseif ($_.AdapterRAM) { $total = [uint64]$_.AdapterRAM }
  $result.gpus += [ordered]@{ name = $_.Name; vramTotalBytes = $total }
}

# GPU 利用率：取所有引擎实例的最大值（实例名含多进程/多引擎，max 更接近整机占用）
# 中文 Windows 计数器对象名可能是本地化的，英文优先、中文兜底
foreach ($path in @('\GPU Engine(*)\Utilization Percentage', '\GPU Engine(*)\利用率百分比')) {
  try {
    $s = (Get-Counter -Counter $path -ErrorAction Stop).CounterSamples
    $result.utilPercent = [math]::Round((($s | Measure-Object -Property CookedValue -Maximum).Maximum), 1)
    break
  } catch {}
}

# 专用显存占用：各适配器 Dedicated Usage 求和
foreach ($path in @('\GPU Adapter Memory(*)\Dedicated Usage', '\GPU Adapter Memory(*)\专用使用率')) {
  try {
    $s = (Get-Counter -Counter $path -ErrorAction Stop).CounterSamples
    $result.vramUsedBytes = [uint64](($s | Measure-Object -Property CookedValue -Sum).Sum)
    break
  } catch {}
}

ConvertTo-Json -InputObject ([pscustomobject]$result) -Depth 3
"""


def _gpu_windows_counters() -> Optional[dict]:
    """调用 PowerShell 采集 Windows GPU 信息，返回 JSON dict；失败返回 None"""
    if os.name != "nt":
        return None
    try:
        enc = base64.b64encode(_PS_GPU_SCRIPT.encode("utf-16-le")).decode("ascii")
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
            capture_output=True,
            timeout=30,
        )
        return json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except Exception:
        return None


def _name_match(a: str, b: str) -> bool:
    """NVIDIA 名称（CIM 与 pynvml）可能略有差异，用小写包含关系做模糊匹配"""
    a, b = a.lower().strip(), b.lower().strip()
    return a in b or b in a


def _gpu_info() -> list:
    """合并三层采集结果，返回统一的 GPU 信息列表"""
    nvidia = _gpu_nvidia()
    amd = _gpu_amd()
    win = _gpu_windows_counters()

    gpus = []
    if win:
        fallback_util = win.get("utilPercent")
        fallback_vram_used = win.get("vramUsedBytes")
        win_gpus = win.get("gpus") or []
        # 有独立显卡时跳过 Microsoft 虚拟适配器（RDP/Basic Render），避免噪音
        has_discrete = any(
            not (g.get("name") or "").lower().startswith("microsoft")
            for g in win_gpus
        )
        for g in win_gpus:
            name = g.get("name") or "未知显卡"
            if has_discrete and name.lower().startswith("microsoft"):
                continue

            # NVIDIA：pynvml 数据精确，优先采用
            nv = next((n for n in nvidia if _name_match(n["name"], name)), None)
            if nv:
                gpus.append(nv)
                continue

            total = g.get("vramTotalBytes") or 0
            # AMD：pyadl 温度/利用率尽力补充
            extra = next((v for k, v in amd.items() if _name_match(k, name)), {})
            util = extra.get("util")
            if util is None:
                util = fallback_util if total else None  # 虚拟/核显不给全局利用率，避免误导
            vram_used = fallback_vram_used if (total and fallback_vram_used is not None) else None
            gpus.append({
                "name": name,
                "util": util,
                "mem_used_bytes": vram_used,
                "mem_total_bytes": total or None,
                "temp": extra.get("temp"),
            })
    else:
        # 非 Windows：仅有 pynvml 数据可用
        gpus = list(nvidia)
    return gpus


def _cpu_model() -> str:
    """CPU 型号：Windows 读注册表，Linux 读 /proc/cpuinfo，失败回退 platform"""
    try:
        if os.name == "nt":
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                return str(name).strip()
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "未知 CPU"


def _collect_metrics() -> dict:
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(_disk_path())
    return {
        "hostname": socket.gethostname(),
        "ip": _local_ip(),
        "os": f"{platform.system()} {platform.release()}",
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "cpu_count": psutil.cpu_count(logical=True),
        "cpu_model": _cpu_model(),
        "memory_percent": vm.percent,
        "memory_total_gb": round(vm.total / (1024 ** 3), 2),
        "memory_used_gb": round(vm.used / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
    }


def _format_gpus(gpus: list) -> str:
    if not gpus:
        return "显卡: 未检测到可用 GPU 信息"
    lines = []
    for i, g in enumerate(gpus, 1):
        parts = []
        if g.get("util") is not None:
            parts.append(f"利用率 {g['util']}%")
        total = g.get("mem_total_bytes")
        used = g.get("mem_used_bytes")
        if total:
            total_gb = total / (1024 ** 3)
            if used:
                parts.append(f"显存 {used / (1024 ** 3):.1f}GB / {total_gb:.1f}GB")
            else:
                parts.append(f"显存总量 {total_gb:.1f}GB")
        if g.get("temp") is not None:
            parts.append(f"温度 {g['temp']}℃")
        detail = ("，" + "，".join(parts)) if parts else "（该驱动暂不支持利用率/显存查询）"
        lines.append(f"- GPU{i} {g['name']}{detail}")
    return "显卡:\n" + "\n".join(lines)


def collect_status() -> dict:
    """公共接口：供 FastAPI 端点与 LangChain 工具共用，返回实时指标 + GPU 信息"""
    data = _collect_metrics()
    data["gpus"] = _gpu_info()
    return data


@tool
def get_server_status(server: str = "local") -> str:
    """
    查询本机（当前服务器）的实时运行状态，返回 CPU、内存、磁盘、显卡(GPU)利用率/显存、
    主机名、IP、操作系统等实时指标。
    当用户询问"当前服务器状态/本机 CPU/实时内存/磁盘使用率/显卡型号/GPU 占用率/设备实时数据"
    等需要实时数据的问题时调用此工具。
    注意：本工具只返回当前所在机器的实时快照；如需查询运维数据库中多台服务器的历史/聚合数据，请改用 nl2sql_query。

    Args:
        server: 服务器标识，目前仅支持本机，可传 "local" 或留空
    """
    try:
        m = _collect_metrics()
        gpu_text = _format_gpus(_gpu_info())
        return (
            f"主机名: {m['hostname']}\n"
            f"IP: {m['ip']}\n"
            f"操作系统: {m['os']}\n"
            f"CPU 使用率: {m['cpu_percent']}% (逻辑核数 {m['cpu_count']})\n"
            f"CPU 型号: {m['cpu_model']}\n"
            f"内存使用率: {m['memory_percent']}% "
            f"({m['memory_used_gb']}GB / {m['memory_total_gb']}GB)\n"
            f"磁盘使用率: {m['disk_percent']}% "
            f"({m['disk_used_gb']}GB / {m['disk_total_gb']}GB)\n"
            f"{gpu_text}"
        )
    except Exception as e:
        return f"采集实时服务器状态失败: {e}"


def _top_memory_processes(limit: int = 3) -> list:
    """按内存占用率取前 N 个进程，返回 (名称, PID, 内存占用率%, RSS字节) 列表"""
    procs = []
    for p in psutil.process_iter(["name", "memory_percent", "memory_info"]):
        try:
            info = p.info
            name = info["name"] or f"PID-{p.pid}"
            rss = info["memory_info"].rss if info["memory_info"] else 0
            procs.append((name, p.pid, info["memory_percent"] or 0.0, rss))
        except Exception:
            continue  # 系统保护进程可能拒绝访问，跳过
    procs.sort(key=lambda x: x[2], reverse=True)
    return procs[:limit]


@tool
def get_top_processes(limit: int = 3) -> str:
    """
    查询当前占用内存最高的前 N 个进程（默认前 3）。
    当用户询问"为什么内存占用这么高"、"哪个软件最占内存"、"内存被什么占用了"、
    "内存占用高怎么办"等进程级问题时调用此工具，结合 get_server_status 的总体
    内存使用率分析原因并给出优化建议。

    Args:
        limit: 返回的进程数量，默认 3，最大 10
    """
    try:
        limit = max(1, min(int(limit), 10))
        procs = _top_memory_processes(limit)
        if not procs:
            return "未能获取进程内存信息。"
        lines = [f"当前内存占用最高的前 {len(procs)} 个进程："]
        for i, (name, pid, mpct, rss) in enumerate(procs, 1):
            lines.append(f"{i}. {name} (PID {pid})：占用 {mpct:.1f}%，约 {rss / 1024 ** 3:.2f}GB")
        return "\n".join(lines)
    except Exception as e:
        return f"采集进程内存信息失败: {e}"


registry.register(get_server_status)
registry.register(get_top_processes)
