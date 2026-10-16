"""文件职责：打包本项目可独立查看的Keil/CubeMX答辩工程。
主要功能：复制实际依赖、校验引用与Flash边界、排除私有运行资料、输出SHA256清单和ZIP。
技术栈：Python pathlib/XML/zipfile/hashlib；关联当前CubeMX工程、下载工具及验收文档。
编写/修改日期（日志对应）：2026-10-15（归档与联调）、2026-10-16（供气演示与交付）；交付文件日期取实际执行日期。
"""
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from intelhex import IntelHex
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'firmware/stm32f103_hardware_test/CubeMX'


def private_values():
    """仅在内存提取本机私密值用于泄漏检查；不输出值、不将配置复制进交付包。"""
    values = []
    for key, value in dotenv_values(ROOT / '.env').items():
        if value and len(value) >= 8 and any(part in key.upper() for part in ('PASSWORD', 'TOKEN', 'API_KEY', 'SECRET')):
            values.append(value.encode())
    wifi = ROOT / '.runtime/wifi.json'
    if wifi.is_file():
        def walk(data):
            """递归检查私有配置，只选密码、令牌及密钥，不把非敏感网络地址误报为秘密。"""
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, str) and len(value) >= 8 and any(part in key.lower() for part in ('password', 'token', 'secret')):
                        values.append(value.encode())
                    else:
                        walk(value)
            elif isinstance(data, list):
                for item in data:
                    walk(item)
        walk(json.loads(wifi.read_text(encoding='utf-8-sig')))
    return values


def main():
    """只从明确的工程根复制白名单目录；引用、私密扫描和ZIP完整性全部通过才报告成功。"""
    today = datetime.now().strftime('%Y-%m-%d')
    output = ROOT.parent / 'outputs' / ('system-defense-' + today.replace('-', ''))
    output.mkdir(parents=True, exist_ok=True)
    destination = output / 'KitchenSentinel_Keil'
    project_base = destination / 'firmware/stm32f103_hardware_test'
    cube = project_base / 'CubeMX'
    cube.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in SOURCE.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(SOURCE)
        if any(part in ('__pycache__', '.runtime', '.git') for part in relative.parts):
            continue
        if path.name.startswith('KeilEntryCheck') or path.name.endswith(('.uvguix.lenovo', '.bak', '.pyc')):
            continue
        # 用户界面会话与临时退出码检查不属于项目；Output保留实际构建/导航所需文件。
        if relative.parts[0] == 'MDK-ARM' and path.suffix not in ('.uvprojx', '.uvoptx'):
            continue
        target = cube / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(target)
    shutil.copy2(SOURCE.parent / 'README.md', project_base / 'README.md')
    docs = destination / 'docs'
    docs.mkdir(exist_ok=True)
    for name in ('Keil工程与答辩代码导览_2026-10-15.md', '系统升级与离线报表验收_2026-10-16.md', '代码注释规范与模块索引.md', '供气与通知及中文界面验收_2026-10-16.md', '功能演示录制与答辩指南_2026-10-16.md', '答辩上手速查_2026-10-16.md'):
        shutil.copy2(ROOT / 'docs' / name, docs / name)
    (destination / 'requirements-download.txt').write_text('pyocd==0.45.1\n', encoding='utf-8')
    (destination / '打开与下载说明.md').write_text(
        '# Keil / CubeMX 一体工程\n\n交付日期：' + today + '\n\n'
        '打开firmware/stm32f103_hardware_test/CubeMX/MDK-ARM/KitchenSentinel_F103.uvprojx。'
        '选择Template只编译，Download目标F7执行真实下载与逐字节校验。\n\n'
        '完整项目可直接使用现有.venv。独立包在本文件同层执行python -m venv .venv，'
        '再执行.venv\\Scripts\\python.exe -m pip install -r requirements-download.txt。'
        '保留目录嵌套，以便Keil定位本包.venv。安装Keil ARMCC5和原厂器件包仍属于开发工具环境。\n\n'
        'CubeMX配置为firmware/stm32f103_hardware_test/CubeMX/KitchenSentinel_F103.ioc，'
        '与实际Core/Drivers工程位于同根目录。换位置后Rebuild All，再Go To Definition。\n\n'
        '工程包不含热点密码、设备令牌、数据库配置、完整Flash备份或本机环境。'
        '烧录只覆盖应用区，保留板上离线队列及私有配置；首次在新板使用仍需完整项目配置网络。'
        '上电默认待机，开启采样须通过完整系统设备启用页。详细证据与边界见docs。\n', encoding='utf-8')
    project = cube / 'MDK-ARM/KitchenSentinel_F103.uvprojx'
    references = []
    for node in ET.parse(project).findall('.//FilePath'):
        path = (project.parent / node.text).resolve()
        if not path.is_relative_to(cube.resolve()) or not path.is_file():
            raise RuntimeError('交付工程存在缺失或越界文件引用')
        references.append(path)
    image = IntelHex(str(cube / 'Output/atk_f103.hex'))
    if image.minaddr() != 0x08000000 or image.maxaddr() >= 0x0800A000:
        raise RuntimeError('应用HEX越过40KiB分区，停止交付')
    secrets = private_values()
    manifest = {'created_at': datetime.now().astimezone().isoformat(), 'firmware': 'stm32f103-hwtest/7.0',
                'unique_project_references': len(set(references)), 'hex_bytes': len(image.addresses()), 'files': {}}
    for path in sorted(destination.rglob('*')):
        if not path.is_file() or path.name == 'manifest.json':
            continue
        content = path.read_bytes()
        if any(secret in content for secret in secrets):
            raise RuntimeError('交付文件命中私密值检查，停止打包；检查文件：' + str(path.relative_to(destination)))
        manifest['files'][path.relative_to(destination).as_posix()] = hashlib.sha256(content).hexdigest()
    manifest['private_scan_passed'] = True
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = output / ('Keil_CubeMX一体工程_' + today + '.zip')
    with ZipFile(archive, 'w', compression=ZIP_DEFLATED, compresslevel=6) as stream:
        for path in sorted(destination.rglob('*')):
            if path.is_file():
                stream.write(path, path.relative_to(output))
    with ZipFile(archive) as stream:
        if stream.testzip() is not None:
            raise RuntimeError('ZIP完整性检查失败')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / (archive.name + '.sha256')).write_text(digest + '  ' + archive.name + '\n', encoding='utf-8')
    print(json.dumps({'zip': str(archive), 'files': len(manifest['files']), 'local_refs': len(set(references)),
                      'hex_bytes': manifest['hex_bytes'], 'private_scan_passed': True, 'bytes': archive.stat().st_size,
                      'sha256': digest}, ensure_ascii=False))


if __name__ == '__main__':
    main()
