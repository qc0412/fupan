#!/usr/bin/env python3
"""
开盘啦(com.aiyu.kaipanla 5.23.0.4) 请求签名算法 —— 从 libsockSign.so 逆向还原

背景: 2026-06-10 起开盘啦服务器开始对请求验签, 无签名的裸脚本直连返回 Count:0(空数据)。
签名由 native 函数 Java_com_aiyu_kaipanla_newindex_data_SocketRepository_signature 计算。
该函数(@0x5f450, libsockSign.so arm64)逆向结论:

  明文 = "kpl-2025" + ":" + arg3 + ":" + "1" + ":" + versionName
              + ":" + arg2 + ":" + arg1 + ":" + channelID
  sign = md5( 明文[:36] ).hexdigest()       # 注意: 先对明文取前36字符(substring(0,36)) 再 MD5

已确定(静态铁证):
  - salt           = "kpl-2025"             (硬编码字符串 @0x46e1d)
  - 固定项 "1"                               (@0x46aca)
  - 分隔符 ":"                               (@0x47204)
  - versionName    = 5.23.0.4 (APK versionName, 应与请求 VerSion 参数一致)
  - channelID      = Config.channelID 字段 (候选 kpl / yYB ...)
  - 算法           = MD5 (常量 0xd76aa478 等 + ror25/20/15/10 + F函数, 100%确认)
  - 输出           = 16字节小端 -> 32位 hex

未确定(在360加固的 classes.dex 里, 静态拿不到, 需 1 条真实带 sign 的请求样本反推):
  - arg1 / arg2 / arg3  : Java 层 SocketRepository 调 signature() 传入的 3 个字符串
                          (substring(0,36) 决定签名主要由 salt+arg3 前缀决定)
  - sign 放在请求的哪个参数名 (候选 sign/Sign/Signature/VerifyCode...)
"""
import hashlib

SALT = "kpl-2025"
VERSION_NAME = "5.23.0.4"

def kpl_sign(arg1: str, arg2: str, arg3: str,
             channel_id: str = "kpl", version_name: str = VERSION_NAME) -> str:
    plain = f"{SALT}:{arg3}:1:{version_name}:{arg2}:{arg1}:{channel_id}"
    return hashlib.md5(plain[:36].encode("utf-8")).hexdigest()

if __name__ == "__main__":
    # demo
    print("plain示例:", f"{SALT}:<arg3>:1:{VERSION_NAME}:<arg2>:<arg1>:<channelID>")
    print("sign示例 :", kpl_sign("a1", "a2", "a3"))
