"""文件职责：密码与令牌摘要工具。
主要功能：生成 SHA-256 令牌摘要，使用随机盐和 PBKDF2 保存并校验密码。
技术栈：Python hashlib、secrets、hmac、PBKDF2。
模块联动：auth 登录校验密码，dependencies 验证会话与设备身份，bootstrap 初始化凭据。
编写/修改日期（日志对应）：2026-09-30。
"""

import hashlib
import hmac
import secrets


def digest(value: str) -> str:
    """计算固定长度 SHA-256 摘要；数据库只保存摘要，不保存原始令牌。
    编写/修改日期（日志对应）：2026-09-30。
    """
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str) -> str:
    """使用随机盐和 PBKDF2 派生密码摘要，便于后续升级迭代次数。
    编写/修改日期（日志对应）：2026-09-30。
    """
    salt = secrets.token_hex(16)
    result = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600_000).hex()
    return f'pbkdf2_sha256$600000${salt}${result}'


def verify_password(password: str, encoded: str) -> bool:
    """校验密码摘要；遇到历史脏数据时返回失败而不是让登录接口报错。
    编写/修改日期（日志对应）：2026-09-30。
    """
    try:
        _, iterations, salt, expected = encoded.split('$')
        result = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(iterations)).hex()
        return hmac.compare_digest(result, expected)
    except (ValueError, TypeError):
        return False
