# -*- coding: utf-8 -*-
"""
services/ai_client.py — 腾讯云 LKE（大模型知识引擎）客户端

核心能力：
1. TC3（Signature V3）鉴权：使用 SECRET_ID / SECRET_KEY 生成符合腾讯云规范的签名 Headers
2. stream_chat：SSE 流式对话，返回异步生成器
3. evaluate_doctor：收集完整流式响应后解析 JSON 评分结果
"""

import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timezone
from typing import AsyncGenerator
from urllib.parse import urlparse

import httpx
from httpx_sse import aconnect_sse


class TencentLKEClient:
    """
    腾讯云 LKE 知识引擎客户端。

    鉴权方案：TC3-HMAC-SHA256（腾讯云 API Signature V3）
    参考文档：https://cloud.tencent.com/document/api/1093/107760
    """

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        bot_app_key: str,
        sse_url: str,
        service: str = "lke",
        region: str = "",
    ) -> None:
        if not all([secret_id, secret_key, bot_app_key, sse_url]):
            raise ValueError("secret_id / secret_key / bot_app_key / sse_url 均为必填项")

        self.secret_id = secret_id
        self.secret_key = secret_key
        self.bot_app_key = bot_app_key
        self.sse_url = sse_url
        self.service = service
        self.region = region

        # 解析 URL 拆分 host 和 path（签名时需要分开使用）
        parsed = urlparse(sse_url)
        self.host: str = parsed.netloc   # e.g. "wss.lke.cloud.tencent.com"
        self.path: str = parsed.path     # e.g. "/v1/qbot/chat/sse"

    # ------------------------------------------------------------------ #
    #  TC3 签名实现                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _hmac_sha256(key: bytes, msg: str) -> bytes:
        """使用 HMAC-SHA256 对消息进行签名，返回 bytes"""
        return hmac.new(key, msg.encode("utf-8"), digestmod=hashlib.sha256).digest()

    def _build_auth_headers(self, payload_bytes: bytes) -> dict[str, str]:
        """
        构造腾讯云 TC3-HMAC-SHA256 鉴权 Headers。

        签名步骤（严格按腾讯云文档）：
        Step 1 → CanonicalRequest（规范请求字符串）
        Step 2 → StringToSign（待签字符串）
        Step 3 → DerivedSigningKey → Signature（签名值）
        Step 4 → Authorization Header
        """
        algorithm = "TC3-HMAC-SHA256"
        timestamp = int(time.time())

        # UTC 日期，格式 YYYY-MM-DD，用于派生签名密钥
        date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

        # ── Step 1: 规范请求 ──
        http_method = "POST"
        canonical_uri = self.path
        canonical_querystring = ""  # 无查询参数
        # Headers 必须小写且升序排列，末尾加换行
        canonical_headers = (
            f"content-type:application/json\n"
            f"host:{self.host}\n"
        )
        signed_headers = "content-type;host"
        # 请求体的 SHA256 哈希（小写十六进制）
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        canonical_request = "\n".join([
            http_method,
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash,
        ])

        # ── Step 2: 待签字符串 ──
        credential_scope = f"{date}/{self.service}/tc3_request"
        hashed_canonical_request = hashlib.sha256(
            canonical_request.encode("utf-8")
        ).hexdigest()
        string_to_sign = "\n".join([
            algorithm,
            str(timestamp),
            credential_scope,
            hashed_canonical_request,
        ])

        # ── Step 3: 派生签名密钥 → 计算签名 ──
        # 密钥派生链：TC3+SecretKey → date → service → tc3_request
        secret_date = self._hmac_sha256(f"TC3{self.secret_key}".encode("utf-8"), date)
        secret_service = self._hmac_sha256(secret_date, self.service)
        secret_signing = self._hmac_sha256(secret_service, "tc3_request")
        # 最终签名为十六进制字符串
        signature = hmac.new(
            secret_signing, string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).hexdigest()

        # ── Step 4: Authorization Header ──
        authorization = (
            f"{algorithm} "
            f"Credential={self.secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        headers: dict[str, str] = {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Host": self.host,
            "X-TC-Timestamp": str(timestamp),
        }
        if self.region:
            headers["X-TC-Region"] = self.region

        return headers

    # ------------------------------------------------------------------ #
    #  LKE SSE 响应解析                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_text_from_event(data: dict) -> str:
        """
        从 LKE SSE 事件数据中提取文本内容。

        实际返回格式：
          {"type": "reply", "payload": {"is_from_self": false, "is_final": false, "content": "累积全文"}}

        过滤规则：
          - type != "reply" → 忽略（thought / token_stat 等）
          - payload.is_from_self == True → 忽略（用户输入的回显）
        """
        if data.get("type") != "reply":
            return ""

        payload = data.get("payload", {})

        # is_from_self=True 时是对用户输入的回显，跳过
        if payload.get("is_from_self", True):
            return ""

        return payload.get("content", "")

    # ------------------------------------------------------------------ #
    #  公开接口                                                             #
    # ------------------------------------------------------------------ #

    # 默认患者人设（无 kb_query 时的兜底，向后兼容）
    _DEFAULT_PATIENT_ROLE: str = (
        "你现在是一名正在就诊的真实患者。"
        "请完全沉浸在角色中，用患者的口吻回答医生的每一个问题。"
        "绝对不要询问医生【要接诊谁】或【要问诊还是诊断】之类的话，"
        "只要医生打招呼或开口，你就直接诉说你现在的症状和不舒服的地方。"
        "保持角色，不要跳出患者身份。"
    )

    @staticmethod
    def build_patient_role(kb_query: str) -> str:
        """
        构建 RAG 驱动的患者扮演角色指令。

        有 kb_query 时：注入知识库检索指令，让 LKE 根据检索结果扮演具体患者。
        无 kb_query 时：回退到通用患者人设（向后兼容旧病例数据）。
        """
        if not kb_query:
            return TencentLKEClient._DEFAULT_PATIENT_ROLE
        return (
            f"你是一个虚拟患者扮演系统。请立刻在知识库中精准检索包含以下复合特征的档案："
            f"【{kb_query}】，并以此病历为唯一依据，沉浸式扮演该患者。"
            f"绝不能复述病历，绝不能承认自己是AI。"
            f"若因网络或解析问题未检索到，请根据特征自行合理模拟该患者进行求诊。\n"
            f"扮演规则：\n"
            f"① 用符合患者身份（如农民、工人）的朴实口语自然回答；\n"
            f"② 医生没有主动询问的信息不要一次性全部说完；\n"
            f"③ 绝对不要问医生【要接诊谁】之类的话，直接进入角色开始诉说症状；\n"
            f"④ 始终保持患者角色，无论被问什么都不能跳出扮演。"
        )

    async def stream_chat(
        self,
        session_id: str,
        doctor_message: str,
        system_role: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式对话接口，返回异步生成器，逐 token yield 文本内容。

        Args:
            session_id:     会话唯一标识（建议使用 ConsultationRecord.id）
            doctor_message: 医生（学员）输入的问诊内容
            system_role:    可选，覆盖默认患者人设（评分时传入考官人设）
        Yields:
            str: 每个文本 token
        """
        payload: dict = {
            "bot_app_key": self.bot_app_key,
            "visitor_biz_id": f"user_{session_id}",
            "session_id": f"sess_{session_id}",
            "content": doctor_message,
            "visitor_labels": [],
            # 关闭腾讯云默认开场白工作流，防止机器人问"接诊谁"等无关问题
            "workflow_status": "disable",
            # 注入角色：未传入时使用患者人设；evaluate_doctor 时传入考官人设
            "system_role": system_role if system_role is not None else self._DEFAULT_PATIENT_ROLE,
        }
        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = self._build_auth_headers(payload_bytes)

        # ── 探头①：打印发出的完整请求体（确认入参正确）──────────────────────
        print("=" * 60)
        print("【探头① 请求入参】")
        print(f"  URL     : {self.sse_url}")
        print(f"  payload : {json.dumps(json.loads(payload_bytes), ensure_ascii=False)}")
        print("=" * 60)

        try:
            # 腾讯云每次返回的 content 是从头累积的完整字符串，需要切片取增量
            last_length: int = 0

            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                async with aconnect_sse(
                    client,
                    "POST",
                    self.sse_url,
                    headers=headers,
                    content=payload_bytes,
                ) as event_source:
                    async for sse in event_source.aiter_sse():
                        # ── 探头②：打印每一条原始 SSE 事件（不做任何过滤）──────
                        print(f"【探头② 原始SSE事件】 event={sse.event!r}  id={sse.id!r}")
                        print(f"                     data={sse.data!r}")

                        raw_data = sse.data
                        if not raw_data or raw_data.strip() in ("[DONE]", ""):
                            print("  → 跳过（空包 / [DONE]）")
                            continue

                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError as je:
                            # 非 JSON 数据（如心跳包），跳过
                            print(f"  → JSON 解析失败，跳过: {je}")
                            continue

                        # ── 探头③：打印解析后的 dict 结构 ────────────────────
                        print(f"  → 解析后 dict 顶层 keys: {list(data.keys())}")

                        full_text = self._extract_text_from_event(data)

                        # ── 探头④：打印提取结果 ───────────────────────────────
                        print(f"  → _extract_text_from_event 返回(累积长度={len(full_text)}): {full_text!r}")

                        if not full_text:
                            continue

                        # 增量切片：只取本次新生成的部分
                        delta = full_text[last_length:]
                        last_length = len(full_text)

                        print(f"  → delta(新增={len(delta)}字): {delta!r}")

                        if delta:
                            yield delta

        except httpx.HTTPStatusError as e:
            print(f"\033[91m【探头⑤ HTTP错误】 status={e.response.status_code}  body={e.response.text[:300]}\033[0m")
            raise RuntimeError(
                f"LKE API 返回错误状态码 {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            print(f"\033[91m【探头⑤ 网络错误】 {e}\033[0m")
            raise RuntimeError(f"LKE API 网络请求失败: {e}") from e
        except Exception as e:
            # 捕获所有其他异常，防止被上层 RuntimeError 处理器吞掉
            print(f"\033[91m【探头⑤ 未知异常】 {type(e).__name__}: {e}\033[0m")
            raise

    async def evaluate_doctor(
        self,
        aggregated_data: str,
        kb_query: str = "",
    ) -> dict:
        """
        评判医生的问诊表现，返回 JSON 格式的评分结果。

        使用 RAG 模式：不再本地注入标准答案，而是让 LKE 通过 kb_query
        自动检索知识库中的标准诊断方案，再据此对学员评分。

        Args:
            aggregated_data: 聚合的对话记录 + 检查记录文本
            kb_query:        知识库检索关键词，用于定位该案例的标准答案
        Returns:
            dict: {"score": int, "evaluation": str}
        """
        # ── 开发者金手指（DEV CHEAT CODE）─────────────────────────────────
        # 在最终诊断字段中检测到 "SVIP"（不区分大小写）时，
        # 跳过 AI 评分直接返回满分，用于非医学背景开发者测试关卡解锁功能。
        if re.search(r"svip", aggregated_data, re.IGNORECASE):
            print("【金手指激活】检测到 SVIP，跳过 AI 评分，直接返回满分。")
            return {
                "score": 100,
                "evaluation": "🕵️‍♂️ 开发者模式：金手指已激活，强制满分通关！",
            }

        # 构造判卷 Prompt：RAG 检索标准答案 + 严格评分规则
        divider = "=" * 40
        kb_instruction = (
            f"请立刻在知识库中精准检索包含以下复合特征的档案：【{kb_query}】，"
            f"并以此病历为唯一依据进行评分。"
            f"若因网络或解析问题未检索到，请根据该特征的临床医学标准自行判断，绝不准承认找不到。"
            if kb_query else
            "请根据通用临床诊断规范和医学标准进行评分。"
        )
        eval_prompt = f"""你是一名极其严厉的主任医师考官。{kb_instruction}
你的职责是客观、严格地对学员的问诊表现进行量化评分，绝不手软。

{divider}
【评分规则（满分100分）】
{divider}

基础分：100分

必扣分项：
- 少做一项必要检查（标准答案中的必查项目）：每缺一项 -10分
- 多做一项无指征的过度检查（学员使用但标准答案未包含）：每多做一项 -5分
  （过度检查是乱花金币、浪费医疗资源的恶劣行为，必须严惩）
- 最终诊断与标准答案严重不符：直接判定不及格，总分上限49分
- 门诊记录完全空白或主诉/现病史均未填写：-10分

【医疗经济学】评分维度（必须严格执行）：
- 若考生消耗超过初始预算 40% 的金币，但诊断结论简单或存在大量无效检查，
  必须在点评中严厉批评其"过度医疗、浪费医疗资源、加重患者经济负担"，并扣除 5~15 分。
- 若考生消耗金币极少（不超过初始预算 10%）甚至为 0，且最终诊断完全正确，
  必须在点评中大力表扬其"临床基本功扎实，具有极高的医疗经济学素养"，并酌情加 5~10 分。

酌情加分（最多+10分，不超过100分上限）：
- 剩余金币较多（效费比高，避免了过度医疗）：+1~5分
- 门诊记录要素齐全且条理清晰：+1~5分

{divider}
【学员诊断过程】
{divider}
{aggregated_data}

{divider}
【输出要求（严格遵守）】
{divider}
你的 evaluation 评语必须包含一段专门针对考生"检查花费"的评价（表扬或批评均可，视实际情况而定）。
严格只输出以下 JSON，禁止任何额外文字或 Markdown 代码块：
{{"score": 85, "evaluation": "此处填写200字以内的严厉评语，必须包含针对检查花费的专项评价并明确指出扣分原因"}}"""

        # 考官人设：强制 JSON 输出，绝不扮演患者
        evaluator_role = (
            "你是一名严格的医学考官助手，同时精通医疗经济学。"
            "你的唯一职责是根据给定的评分规则和标准答案对学员进行评分。"
            "在评分时，你必须严格审查考生的【经济学指标】："
            "若花费超过初始预算 40% 却未带来关键诊断价值，必须予以严厉批评并扣分；"
            "若花费极少甚至为零却得出正确诊断，必须大力表扬。"
            "你的最终输出必须是一个合法的 JSON 字符串，绝不能包含任何多余的解释文字和 Markdown 标记。"
            'JSON 格式必须严格为：{"score": 具体整数分数, "evaluation": "你的详细点评，其中必须含有针对检查花费的专项评价"}。'
            "禁止在 JSON 前后添加任何文字，禁止使用 ```json 代码块包裹。"
        )

        collected: list[str] = []
        eval_session_id = f"eval_{int(time.time())}"

        try:
            async for chunk in self.stream_chat(
                session_id=eval_session_id,
                doctor_message=eval_prompt,
                system_role=evaluator_role,
            ):
                collected.append(chunk)

            full_text = "".join(collected).strip()
            print(f"【评分原始输出】 {full_text!r}")

            # ── 第一步：去除 Markdown 代码块包裹 ──────────────────────────────
            clean = re.sub(r"^```(?:json)?\s*", "", full_text)
            clean = re.sub(r"\s*```\s*$", "", clean).strip()

            # ── 第二步：尝试直接 JSON.parse ───────────────────────────────────
            try:
                obj = json.loads(clean)
                if "score" in obj:
                    return {"score": int(obj["score"]), "evaluation": str(obj.get("evaluation", ""))}
            except (json.JSONDecodeError, ValueError):
                pass

            # ── 第三步：正则精确提取 score + evaluation ───────────────────────
            pattern_exact = re.compile(
                r'\{\s*"score"\s*:\s*(\d+(?:\.\d+)?)\s*,\s*"evaluation"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}',
                re.DOTALL,
            )
            m = pattern_exact.search(full_text)
            if m:
                return {
                    "score": int(float(m.group(1))),
                    "evaluation": m.group(2).replace('\\"', '"'),
                }

            # ── 第四步：贪婪匹配 {.*}，应对 evaluation 中含嵌套括号的情况 ──────
            m2 = re.search(r"\{.*\}", full_text, re.DOTALL)
            if m2:
                try:
                    obj = json.loads(m2.group())
                    if "score" in obj:
                        return {"score": int(obj["score"]), "evaluation": str(obj.get("evaluation", ""))}
                except (json.JSONDecodeError, ValueError):
                    pass

            # ── 第五步：宽松扫描，找到第一个含 score 的 JSON 对象 ────────────
            for candidate in re.finditer(r"\{[^{}]{10,}\}", full_text, re.DOTALL):
                try:
                    obj = json.loads(candidate.group())
                    if "score" in obj:
                        return {"score": int(obj["score"]), "evaluation": str(obj.get("evaluation", ""))}
                except (json.JSONDecodeError, ValueError):
                    pass

            # ── 第六步：尝试用整个原始文本再解析一次 ──────────────────────────
            return json.loads(full_text)

        except (json.JSONDecodeError, ValueError):
            print(f"【评分解析失败】full_text={full_text!r}")
            return {
                "score": 60,
                "evaluation": "系统评分解析出现异常，已给予基础保底分数。请检查您的问诊记录后联系管理员。",
            }
        except RuntimeError as e:
            return {
                "score": 50,
                "evaluation": f"AI 评分服务连接失败，给予基础分数。原因：{str(e)[:120]}",
            }

    async def extract_medical_data(
        self,
        kb_query: str,
        metric_name: str,
    ) -> str:
        """
        从知识库中提取指定案例特定检查项目的真实数值/描述。

        通过 stream_chat 发起一次独立的数据提取会话（与患者问诊会话完全隔离），
        收集全部流式片段后返回完整文本。

        Args:
            kb_query:    案例复合指纹，如 "糖尿病 A16案例一 陈某某 女 65岁 农民 多饮多尿多食"
            metric_name: 检查项目名称，如 "血糖检测" / "血压测量" / "听诊"
        Returns:
            str: 知识库中关于该项目的原文描述；检索失败时返回通用占位文本
        """
        extractor_role = (
            f"你是一个资深的医学临床助理。\n"
            f"任务：从知识库中提取【{kb_query}】的【{metric_name}】结果。\n\n"
            f"提取逻辑升级：\n"
            f"1. 数值匹配：如果是血糖、血压、体温，请提取具体的数值和单位。\n"
            f"2. 常识映射：如果用户要求提取【听诊】或【触诊】，请去查找'心'、'肺'、'腹'或'全身查体'的描述。"
            f"例如：看到'心肺腹未见异常'，就直接提取这句话作为【听诊】结果。\n"
            f"3. 上下文关联：不要只搜关键字。如果章节里描述了该项的任何状态（如'双下肢无水肿'对应'触诊'），请务必提取。\n"
            f"4. 强制简洁：只给结论，严禁废话。确实找不到任何相关描述才回复'该项未检查'。\n\n"
            f"当前提取目标：【{metric_name}】"
        )
        extract_prompt = kb_query
        session_id = f"extract_{int(time.time())}"

        collected: list[str] = []
        try:
            async for chunk in self.stream_chat(
                session_id=session_id,
                doctor_message=extract_prompt,
                system_role=extractor_role,
            ):
                collected.append(chunk)

            result = "".join(collected).strip()
            print(f"【数据提取】{metric_name} → {result!r}")
            return result if result else "该项未检查"

        except (RuntimeError, Exception) as e:
            print(f"\033[91m【数据提取失败】{metric_name}: {e}\033[0m")
            return "检查服务暂时不可用，请稍后重试"
