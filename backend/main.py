# -*- coding: utf-8 -*-
"""
main.py — 智诊 (SmartDiag) FastAPI 后端主入口

架构原则：
  - 所有业务逻辑（预算管理/状态校验/AI 交互）收敛在后端
  - 前端仅负责渲染和请求发送，不持有任何业务状态
  - SSE 流式响应通过 StreamingResponse + 异步生成器实现

启动命令：
  uvicorn main:app --reload --host 0.0.0.0 --port 28080
"""

import csv
import json
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db
from models import Case, ConsultationRecord, DialogueMessage, InstrumentLog, User
from services.ai_client import TencentLKEClient

# ------------------------------------------------------------------ #
#  环境变量 & 全局配置                                                   #
# ------------------------------------------------------------------ #

load_dotenv()

_REQUIRED_ENV = ["BOT_APP_KEY", "SECRET_ID", "SECRET_KEY", "LKE_SSE_URL"]
for _key in _REQUIRED_ENV:
    if not os.getenv(_key):
        raise EnvironmentError(f"缺少必要环境变量: {_key}，请检查 .env 文件")

# 各器械检查的金币消耗（前后端共同参考标准）
INSTRUMENT_COSTS: dict[str, int] = {
    "体温测量": 10,
    "血氧检测": 20,
    "血压测量": 20,
    "视诊": 30,
    "听诊": 50,
    "叩诊": 50,
    "触诊": 50,
    "心电图": 100,
    "血常规": 100,
    "尿常规": 80,
    "血糖检测": 120,
    "生化检查": 150,
    "超声检查": 200,
    "X光检查": 200,
    "CT检查": 500,
    "核磁共振": 800,
}

# 默认检查结果（当病例未配置该检查项时返回）
DEFAULT_INSTRUMENT_RESULT = "检查未见明显异常，各项指标在正常范围内。"

# ─── 五阶关卡映射 ────────────────────────────────────────────────────────────────
# Case.tencent_kb_id 首字母 → 关卡等级（1-5）
ID_PREFIX_LEVEL: dict[str, int] = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5,
}
LEVEL_LABELS: dict[int, str] = {
    1: "助理医师",
    2: "住院医师",
    3: "主治医师",
    4: "副主任医师",
    5: "主任医师",
}

def _case_level(tencent_kb_id: str) -> int:
    """根据 tencent_kb_id 首字母推算关卡等级（A=1 … E=5）"""
    prefix = (tencent_kb_id or "")[:1].upper()
    return ID_PREFIX_LEVEL.get(prefix, 0)


# ------------------------------------------------------------------ #
#  AI 客户端单例（全生命周期复用）                                          #
# ------------------------------------------------------------------ #

ai_client = TencentLKEClient(
    secret_id=os.getenv("SECRET_ID", ""),
    secret_key=os.getenv("SECRET_KEY", ""),
    bot_app_key=os.getenv("BOT_APP_KEY", ""),
    sse_url=os.getenv("LKE_SSE_URL", ""),
)


# ------------------------------------------------------------------ #
#  30 案例数据库（RAG 驱动，只存储元数据；器械结果由知识库实时提供）             #
# ------------------------------------------------------------------ #

MOCK_CASES: dict[str, dict] = {
    # ====== 初级题库池 A1-A10 ====================================================
    "A1": {
        "title": "多饮多尿的农妇", "initial_gold": 1000,
        "kb_query": "糖尿病 A16案例一 陈某某 女 65岁",
        "instruments": {
            "血压测量": "BP: 130/85mmHg",
            "血糖检测": "空腹血糖: 9.8mmol/L",
            "体温测量": "T: 36.4℃",
            "听诊":   "双肺呼吸音清，心率 80 次/分，律齐。",
            "尿常规": "尿常规：尿糖（++），尿蛋白（-）。",
        },
        "questions": ["1. 初步诊断及诊断依据是什么？", "2. 基层需完善哪些检查？", "3. 现阶段可给予哪些干预措施？"],
    },
    "A2": {
        "title": "血压升高的老农", "initial_gold": 1000,
        "kb_query": "高血压 A6 王某 男 68岁",
        "instruments": {
            "血压测量": "BP: 143/91mmHg",
            "血糖检测": "空腹指尖血糖: 8.2mmol/L",
            "体温测量": "T: 36.5℃",
            "听诊":   "心肺腹未见异常，足背动脉搏动正常。",
            "心电图": "心电图：窦性心律，未见ST-T改变。",
        },
        "questions": ["1. 高血压诊断是否成立？", "2. 首要干预措施是什么？", "3. 是否立即启动药物治疗？"],
    },
    "A3": {
        "title": "体检血糖异常的讲师", "initial_gold": 1000,
        "kb_query": "糖尿病 (A6)案例一 陈某某 女 32岁",
        "instruments": {
            "血压测量": "BP: 128/82mmHg",
            "血糖检测": "空腹: 6.7mmol/L, 餐后2h: 9.2mmol/L",
            "体温测量": "T: 36.4℃",
            "听诊":   "双肺呼吸音清，心率 76 次/分，律齐。",
            "尿常规": "尿常规：尿糖（±），尿蛋白（-）。",
        },
        "questions": ["1. 糖代谢状态属哪种类型？", "2. 是否需要启动药物治疗？", "3. 生活方式干预重点？"],
    },
    "A4": {
        "title": "头晕头胀的男性长者", "initial_gold": 1000,
        "kb_query": "高血压 A11 案例一 张某某 男 68岁",
        "instruments": {
            "血压测量": "BP: 155/95mmHg",
            "血糖检测": "空腹血糖: 5.2mmol/L",
            "体温测量": "T: 36.5℃",
            "听诊":   "心肺腹无异常，心率 78 次/分，律齐。",
            "血常规": "血常规：白细胞 5.6×10⁹/L，心电图正常。",
        },
        "questions": ["1. 诊断及依据是什么？", "2. 降压目标值是多少？", "3. 随访频率及重点？"],
    },
    "A5": {
        "title": "产后血糖偏高的主妇", "initial_gold": 1000,
        "kb_query": "糖尿病 案例A5 女 38岁 产后血糖升高",
        "instruments": {
            "血压测量": "BP: 122/78mmHg",
            "血糖检测": "空腹: 6.7mmol/L, 餐后2h: 8.2mmol/L",
            "体温测量": "T: 36.7℃",
            "听诊":   "心肺腹未见异常，足背动脉搏动清晰。",
            "触诊":   "心肺腹未见异常。",
        },
        "questions": ["1. 糖代谢状态属哪种类型？", "2. 基层应开展哪些健康管理？", "3. 后续评估重点内容？"],
    },
    "A6": {
        "title": "孕期血压升高的孕妇", "initial_gold": 1000,
        "kb_query": "高血压 A9 张某 女 28岁",
        "instruments": {
            "血压测量": "BP: 146/93mmHg",
            "血糖检测": "血糖仪：随机血糖 6.8mmol/L",
            "体温测量": "T: 36.6℃",
            "听诊":   "心率 78 次/分，神志清，心肺腹无异常。胎心 146 次/分。",
        },
        "questions": ["1. 初步诊断是什么？", "2. 需优先采取哪些干预措施？"],
    },
    "A7": {
        "title": "多饮多尿的务农大叔", "initial_gold": 1000,
        "kb_query": "糖尿病 [A11]案例151 张某 男 62岁",
        "instruments": {
            "血压测量": "BP: 125/80mmHg",
            "血糖检测": "空腹血糖: 8.6mmol/L",
            "体温测量": "T: 36.5℃",
            "听诊":   "心肺腹未见异常，足背动脉搏动可。",
            "视诊":   "BMI: 20.8kg/m²。",
        },
        "questions": ["1. 初步诊断是什么？", "2. 基层应采取哪些初步干预措施？"],
    },
    "A8": {
        "title": "反复头晕的高龄农妇", "initial_gold": 1000,
        "kb_query": "高血压 案例一 A1 张翠花 女 71岁",
        "instruments": {
            "血压测量": "BP: 151/90mmHg",
            "血糖检测": "血糖: 5.2mmol/L",
            "体温测量": "T: 36.4℃",
            "听诊":   "双肺呼吸音清，心率 79 次/分，律齐。",
            "尿常规": "尿常规：尿蛋白（-）。",
        },
        "questions": ["1. 诊断及依据是什么？", "2. 降压目标值是多少？", "3. 限盐的具体要求？"],
    },
    "A9": {
        "title": "乏力多饮的退休工人", "initial_gold": 1000,
        "kb_query": "糖尿病 (A7) 案例 赵某某 男 68岁",
        "instruments": {
            "血压测量": "BP: 138/86mmHg",
            "血糖检测": "空腹: 7.9mmol/L, 餐后2h: 11.2mmol/L",
            "体温测量": "T: 36.4℃",
            "听诊":   "双肺呼吸音清，心率 76 次/分，律齐。",
            "生化检查": "糖化血红蛋白(HbA1c): 7.5%。",
        },
        "questions": ["1. 初步诊断及依据是什么？", "2. 是否需要启动药物治疗？", "3. 随访频率及重点？"],
    },
    "A10": {
        "title": "头晕乏力的老农", "initial_gold": 1000,
        "kb_query": "高血压 案例二 A2 李建国 男 66岁",
        "instruments": {
            "血压测量": "BP: 155/93mmHg",
            "血糖检测": "空腹血糖: 6.6mmol/L；OGTT 2h血糖: 7.8mmol/L",
            "体温测量": "T: 36.5℃",
            "听诊":   "双肺呼吸音清，心率 77 次/分，律齐。",
        },
        "questions": ["1. 诊断及依据是什么？", "2. 是否启动药物治疗？", "3. 血糖干预措施？"],
    },
    # ====== 中级题库池 B1-B10 ====================================================
    "B1": {
        "title": "血糖控制不佳的工人", "initial_gold": 800,
        "kb_query": "糖尿病 B16案例二 李某某 男 58岁",
        "instruments": {
            "血压测量": "BP: 138/86mmHg",
            "血糖检测": "空腹: 10.2mmol/L, HbA1c: 8.8%",
            "体温测量": "T: 36.5℃",
            "听诊":   "双肺呼吸音清，心率 86 次/分，律齐。",
            "触诊":   "足背动脉搏动减弱。",
        },
        "questions": ["1. 血糖控制不佳原因？", "2. 药物治疗调整？", "3. 生活方式干预？"],
    },
    "B2": {
        "title": "血压升高的老年农妇", "initial_gold": 800,
        "kb_query": "高血压 B6 张某 女 72岁",
        "instruments": {
            "血压测量": "BP: 165/100mmHg",
            "血糖检测": "空腹血糖: 7.8mmol/L",
            "体温测量": "T: 36.3℃",
            "听诊":   "心率 82 次/分，律齐，瓣膜区无杂音。",
            "生化检查": "LDL-C: 3.6mmol/L。",
        },
        "questions": ["1. 血压控制不佳原因？", "2. 降压目标值？", "3. 方案如何调整？"],
    },
    "B3": {
        "title": "双下肢麻木的农妇", "initial_gold": 800,
        "kb_query": "糖尿病 C16案例三 王某某 女 70岁",
        "instruments": {
            "血压测量": "BP: 142/91mmHg",
            "血糖检测": "空腹: 9.5mmol/L, HbA1c: 8.5%",
            "体温测量": "T: 36.3℃",
            "听诊":   "双肺呼吸音清，心率 84 次/分，律齐。",
            "触诊":   "足背动脉搏动减弱，尿蛋白(+)。",
        },
        "questions": ["1. 诊断及依据是什么？", "2. 降糖目标及药物调整？", "3. 周围神经病变干预？"],
    },
    "B4": {
        "title": "头晕伴下肢乏力的农妇", "initial_gold": 800,
        "kb_query": "高血压 B11案例一 王某某 女 72岁",
        "instruments": {
            "血压测量": "BP: 165/100mmHg",
            "血糖检测": "空腹血糖: 6.8mmol/L",
            "体温测量": "T: 36.4℃",
            "听诊":   "心肺呼吸音清，心率 82 次/分，律齐。",
            "生化检查": "肌酐: 85μmol/L。",
        },
        "questions": ["1. 诊断及依据？", "2. 降压目标及首选药物？", "3. 血糖血脂干预？"],
    },
    "B5": {
        "title": "肢体麻木的男性农民", "initial_gold": 800,
        "kb_query": "糖尿病 [B11]案例152 王某 男 65岁",
        "instruments": {
            "血压测量": "BP: 128/78mmHg",
            "血糖检测": "空腹: 10.2mmol/L, 餐后2h: 13.5mmol/L",
            "体温测量": "T: 36.4℃",
            "听诊":   "双肺呼吸音清，心率 80 次/分，律齐。",
            "触诊":   "双侧足底触觉减退。",
        },
        "questions": ["1. 目前存在哪些问题？", "2. 基层应调整哪些方案？"],
    },
    "B6": {
        "title": "反复头痛的女性职员", "initial_gold": 800,
        "kb_query": "高血压 C11案例一 李某某 女 45岁",
        "instruments": {
            "血压测量": "BP: 163/102mmHg；动态血压24h平均: 156/98mmHg",
            "血糖检测": "空腹血糖: 8.2mmol/L, HbA1c: 7.5%",
            "体温测量": "T: 36.3℃",
            "听诊":   "双肺呼吸音清，心率 88 次/分，律齐。",
        },
        "questions": ["1. 诊断及依据？", "2. 降压目标值？", "3. 综合干预措施？"],
    },
    "B7": {
        "title": "手脚麻木的货车司机", "initial_gold": 800,
        "kb_query": "糖尿病 案例B2 男 55岁",
        "instruments": {
            "血压测量": "BP: 140/88mmHg",
            "血糖检测": "空腹指尖: 8.8mmol/L, HbA1c: 7.9%",
            "体温测量": "T: 36.7℃",
            "听诊":   "心肺腹未见异常，足背动脉搏动减弱。",
            "触诊":   "双侧手脚针刺觉减退。",
        },
        "questions": ["1. 手脚麻木原因？", "2. 治疗措施调整？", "3. 饮食指导重点？"],
    },
    "B8": {
        "title": "头晕双下肢乏力的农妇", "initial_gold": 800,
        "kb_query": "高血压 案例56 张某某 女 68岁",
        "instruments": {
            "血压测量": "BP: 166/101mmHg",
            "血糖检测": "空腹血糖: 6.9mmol/L",
            "体温测量": "T: 36.5℃",
            "听诊":   "双肺呼吸音清，心率 80 次/分，律齐。",
            "生化检查": "LDL-C: 3.6mmol/L。",
        },
        "questions": ["1. 初步诊断及依据？", "2. 降压目标及首选药物？", "3. 随访频率及重点？"],
    },
    "B9": {
        "title": "伴随乏力的社区居民", "initial_gold": 800,
        "kb_query": "糖尿病 案例B1 女 52岁",
        "instruments": {
            "血压测量": "BP: 128/78mmHg",
            "血糖检测": "空腹血糖: 8.0mmol/L",
            "体温测量": "T: 36.8℃",
            "听诊":   "心肺腹未见异常，足背动脉搏动正常。",
            "视诊":   "BMI: 27.5kg/m²。",
        },
        "questions": ["1. 血糖控制是否满意？", "2. 饮食核心指导？", "3. 免费健康服务有哪些？"],
    },
    "B10": {
        "title": "记忆力下降的留守老人", "initial_gold": 800,
        "kb_query": "高血压 B10 李某某 女 68岁",
        "instruments": {
            "血压测量": "BP: 162/102mmHg",
            "血糖检测": "随机血糖: 10.5mmol/L",
            "体温测量": "T: 36.3℃",
            "听诊":   "双肺呼吸音清，心率 82 次/分，律齐。",
            "尿常规": "尿蛋白（±）。",
        },
        "questions": ["1. 血压分级及风险分层？", "2. 基层初步治疗方案？"],
    },
    # ====== 高级题库池 C1-C10 ====================================================
    "C1": {
        "title": "反复低血糖的退休干部", "initial_gold": 500,
        "kb_query": "糖尿病 D16案例四 赵某某 男 62岁",
        "instruments": {
            "血压测量": "BP: 132/82mmHg",
            "血糖检测": "空腹: 4.8mmol/L, HbA1c: 7.6%；动态血糖：夜间低血糖事件 3 次",
            "体温测量": "T: 36.6℃",
            "听诊":   "心率 88 次/分，心尖部 1/6 级收缩期杂音。",
        },
        "questions": ["1. 低血糖原因是什么？", "2. 胰岛素方案如何优化？", "3. 冠心病综合管理？"],
    },
    "C2": {
        "title": "口干伴下肢水肿的教师", "initial_gold": 500,
        "kb_query": "糖尿病 案例D1 女 58岁",
        "instruments": {
            "血压测量": "BP: 132/81mmHg",
            "血糖检测": "空腹: 9.1mmol/L, UACR: 60mg/g",
            "体温测量": "T: 36.6℃",
            "听诊":   "心肺未见异常，心率 79 次/分。",
            "触诊":   "双下肢轻度凹陷性水肿。",
        },
        "questions": ["1. 口服药联合原则？", "2. 中医干预措施？", "3. 血压管理特殊要求？"],
    },
    "C3": {
        "title": "重度水肿尿量减少的农妇", "initial_gold": 500,
        "kb_query": "糖尿病 E16案例五 张某某 女 72岁",
        "instruments": {
            "血压测量": "BP: 156/97mmHg",
            "血糖检测": "空腹: 13.2mmol/L, HbA1c: 10.8%",
            "体温测量": "T: 36.5℃",
            "听诊":   "双肺呼吸音粗，心率 89 次/分，律齐。",
            "生化检查": "肌酐: 290μmol/L, 血钾: 5.5mmol/L。",
        },
        "questions": ["1. 诊断及依据？", "2. 存在哪些危急情况？", "3. 胰岛素方案及风险？", "4. 转诊指征？"],
    },
    "C4": {
        "title": "低血糖伴胸闷的高管", "initial_gold": 500,
        "kb_query": "糖尿病 案例E1 男 48岁",
        "instruments": {
            "血压测量": "BP: 135/85mmHg",
            "血糖检测": "空腹: 3.7mmol/L, HbA1c: 6.2%；CGM提示：TIR < 3.9mmol/L 占 5%",
            "体温测量": "T: 36.5℃",
            "听诊":   "心界无扩大，心率 85 次/分，律齐。",
        },
        "questions": ["1. 降糖调脂原则？", "2. 中医辨证及建议？", "3. 随访管理重点？"],
    },
    "C5": {
        "title": "意识模糊伴呼吸困难的长者", "initial_gold": 500,
        "kb_query": "糖尿病 [E11]案例155 郑某 男 78岁",
        "instruments": {
            "血压测量": "BP: 175/105mmHg",
            "血糖检测": "空腹血糖: 26.8mmol/L, 尿酮体(+++)",
            "体温测量": "T: 37.8℃",
            "听诊":   "双肺呼吸音粗，可闻及少许湿性啰音及哮鸣音。心率 105 次/分，口唇发绀。",
        },
        "questions": ["1. 最可能诊断是什么？", "2. 紧急处理及转诊注意？", "3. 长期管理核心？"],
    },
    "C6": {
        "title": "血压升高伴夜尿的老妇", "initial_gold": 500,
        "kb_query": "高血压 D6 赵某 女 78岁",
        "instruments": {
            "血压测量": "BP: 165/102mmHg",
            "血糖检测": "空腹血糖: 5.7mmol/L",
            "体温测量": "T: 36.4℃",
            "听诊":   "心率 85 次/分，律齐，双肺呼吸音清。",
            "生化检查": "肌酐: 110μmol/L, 尿蛋白(+)。",
        },
        "questions": ["1. 难治性高血压是否成立？", "2. 难控制的病因？", "3. 如何调整方案？"],
    },
    "C7": {
        "title": "反复头痛胸闷的企业高管", "initial_gold": 500,
        "kb_query": "高血压 D11案例一 赵某某 男 56岁",
        "instruments": {
            "血压测量": "BP: 168/103mmHg；动态血压24h平均: 162/101mmHg",
            "血糖检测": "空腹血糖: 5.6mmol/L, LDL-C: 4.2mmol/L",
            "体温测量": "T: 36.6℃",
            "听诊":   "心率 92 次/分，心尖部 2/6 级收缩期杂音。",
        },
        "questions": ["1. 诊断及依据？", "2. 降压及降脂目标？", "3. 中医辨证及措施？"],
    },
    "C8": {
        "title": "剧烈头痛胸闷的卧床老农", "initial_gold": 500,
        "kb_query": "高血压 E6 陈某 男 82岁",
        "instruments": {
            "血压测量": "BP: 183/112mmHg",
            "血糖检测": "空腹血糖: 5.8mmol/L",
            "体温测量": "T: 36.8℃",
            "听诊":   "双肺呼吸音粗，心率 92 次/分，心尖部 3/6 级杂音。",
            "CT检查": "头颅CT：陈旧性梗死灶，尿蛋白(++)。",
        },
        "questions": ["1. 目前紧急情况及处理？", "2. 长期降压目标？", "3. 长期管理方案？"],
    },
    "C9": {
        "title": "头痛心悸伴乏力的农夫", "initial_gold": 500,
        "kb_query": "高血压 E11案例一 刘某某 男 50岁",
        "instruments": {
            "血压测量": "BP: 172/108mmHg",
            "血糖检测": "血钾: 3.5mmol/L, 血糖: 5.5mmol/L",
            "体温测量": "T: 36.7℃",
            "听诊":   "心率 102 次/分，律齐，心肺听诊无干湿啰音。",
            "CT检查": "肾上腺CT：左侧结节(1.5cm)。",
        },
        "questions": ["1. 疑似哪种内分泌高血压？", "2. 筛查指标及要求？", "3. 基层初步处理？"],
    },
    "C10": {
        "title": "阵发性头晕血压骤升的农夫", "initial_gold": 500,
        "kb_query": "高血压 案例70 赵某某 男 65岁",
        "instruments": {
            "血压测量": "BP: 165/102mmHg；动态血压：多次峰值 > 180/110mmHg",
            "血糖检测": "血钾: 3.4mmol/L, ARR: 35",
            "体温测量": "T: 36.5℃",
            "听诊":   "双肺呼吸音清，心率 86 次/分，律齐。",
        },
        "questions": ["1. 诊断及依据？", "2. 进一步检查？", "3. 紧急处理及转诊？"],
    },
}


# ------------------------------------------------------------------ #
#  应用启动：建表 + 种子数据                                               #
# ------------------------------------------------------------------ #

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时自动建表并注入演示数据"""
    Base.metadata.create_all(bind=engine)
    _seed_demo_data()
    yield  # 应用运行中
    # （此处可添加关闭逻辑，如关闭连接池等）


def _load_cases_from_csv() -> list[dict] | None:
    """
    从 backend/cases.csv 加载病例数据（由 data_parser.py 生成）。
    CSV 字段：id, title, level, initial_gold, kb_query,
              bp, blood_sugar, temp, auscultation, x_ray,
              questions (竖线分隔), standard_answers
    返回 dict 列表；文件不存在时返回 None（降级到 MOCK_CASES）。
    """
    csv_path = Path(__file__).parent / "cases.csv"
    if not csv_path.exists():
        return None

    cases: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get("id", "").strip()
            if not code:
                continue
            questions = [q.strip() for q in row.get("questions", "").split("|") if q.strip()]
            # 只保留血压和血糖两项检查（体温/听诊/X光已从题库中移除）
            instruments = {
                k: v for k, v in {
                    "血压测量": row.get("bp", "").strip(),
                    "血糖检测": row.get("blood_sugar", "").strip(),
                }.items() if v
            }
            cases.append({
                "code":             code,
                "title":            row.get("title", code).strip(),
                "initial_gold":     int(row.get("initial_gold", 1000)),
                "kb_query":         row.get("kb_query", code).strip(),
                "questions":        questions,
                "standard_answers": row.get("standard_answers", "").strip(),
                "instruments":      instruments,
            })

    print(f"[SEED] 从 cases.csv 加载了 {len(cases)} 条病例")
    return cases if cases else None


def _seed_demo_data() -> None:
    """
    启动时播种病例数据。
    优先级：cases.csv（真实题库） > MOCK_CASES（30 条内置演示数据）
    触发重新播种条件：病例数不足、或 instrument_results 为空（结构升级检测）。
    """
    db = SessionLocal()
    try:
        a1 = db.query(Case).filter(Case.tencent_kb_id == "A1").first()
        csv_cases = _load_cases_from_csv()
        expected_count = len(csv_cases) if csv_cases else len(MOCK_CASES)
        needs_reseed = (
            db.query(Case).count() < expected_count
            or not (a1 and (a1.standard_answer or {}).get("instrument_results"))
        )

        if needs_reseed:
            # 按外键依赖顺序清空
            db.query(InstrumentLog).delete()
            db.query(DialogueMessage).delete()
            db.query(ConsultationRecord).delete()
            db.query(Case).delete()
            db.flush()

            source = csv_cases if csv_cases else [
                {**{"code": k}, **v, "code": k} for k, v in MOCK_CASES.items()
            ]

            for meta in source:
                code = meta.get("code") or meta.get("id", "")
                db.add(Case(
                    title=meta["title"],
                    patient_prompt="",
                    tencent_kb_id=code,
                    standard_answer={
                        "kb_query":           meta["kb_query"],
                        "questions":          meta["questions"],
                        "standard_answers":   meta.get("standard_answers", ""),
                        "instrument_results": meta.get("instruments", {}),
                    },
                    initial_budget=meta["initial_gold"],
                ))

            src_label = "cases.csv" if csv_cases else "MOCK_CASES"
            print(f"[SEED] 已从 {src_label} 播种 {len(source)} 条病例")

        if db.query(User).count() == 0:
            db.add(User(
                username="doctor01",
                password_hash="$2b$12$demo_hash_placeholder",
                total_score=0.0,
            ))

        db.commit()
    finally:
        db.close()


# ------------------------------------------------------------------ #
#  FastAPI 应用实例                                                      #
# ------------------------------------------------------------------ #

app = FastAPI(
    title="智诊 SmartDiag API",
    description="乡村医生 AI 辅助问诊实训平台后端",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS：允许 Vue 开发服务器（5173）和生产环境跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ #
#  Pydantic 请求/响应 Schema                                            #
# ------------------------------------------------------------------ #

class StartRequest(BaseModel):
    case_id: str = Field(..., description="病例代码，如 'A1'、'B3'")
    user_id: int = Field(..., description="用户 ID")


class ChatRequest(BaseModel):
    record_id: int = Field(..., description="问诊记录 ID")
    doctor_message: str = Field(..., min_length=1, description="医生输入的问诊内容")


class InstrumentRequest(BaseModel):
    record_id: int = Field(..., description="问诊记录 ID")
    action_name: str = Field(..., description="检查项目名称，如 '听诊' 或 '血常规'")


class SubmitRequest(BaseModel):
    record_id: int = Field(..., description="问诊记录 ID")
    final_diagnosis: str = Field(..., min_length=1, description="医生提交的最终诊断")
    doctor_notes: str = Field(default="", description="医生门诊记录（主诉/现病史/既往史）")


# ------------------------------------------------------------------ #
#  辅助函数                                                             #
# ------------------------------------------------------------------ #

def _get_active_record(record_id: int, db: Session) -> ConsultationRecord:
    """获取进行中的问诊记录，若不存在或已结束则抛出 404"""
    record = (
        db.query(ConsultationRecord)
        .filter(
            ConsultationRecord.id == record_id,
            ConsultationRecord.status == "ongoing",
        )
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="问诊记录不存在或已结束，请重新开始问诊",
        )
    return record


# ------------------------------------------------------------------ #
#  路由：GET /api/cases — 获取病例列表（前端选择病例用）                      #
# ------------------------------------------------------------------ #

@app.get("/api/cases", summary="获取病例列表（支持按等级过滤与随机抽取）")
def list_cases(
    level: Optional[int] = None,
    random_pick: bool = False,
    db: Session = Depends(get_db),
):
    """
    - 不传参数：返回全部病例（含 level 字段）
    - level=1~5：仅返回该等级的病例
    - level=2&random_pick=true：从该等级随机抽取一条返回
    若指定等级下无病例，返回 404 并给出友好提示。
    """
    cases = db.query(Case).all()
    result = [
        {
            "id": c.tencent_kb_id,
            "title": c.title,
            "level": _case_level(c.tencent_kb_id),
            "initial_budget": c.initial_budget,
        }
        for c in cases
    ]

    if level is not None:
        result = [r for r in result if r["level"] == level]
        if not result:
            label = LEVEL_LABELS.get(level, f"等级{level}")
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Level {level}（{label}）暂无可用病例。"
                    f"请在 Word 题库中添加对应前缀（{'ABCDE'[level-1]}）的案例，"
                    f"重新运行 data_parser.py 后重启后端。"
                ),
            )

    if random_pick and result:
        result = [random.choice(result)]

    return result


# ------------------------------------------------------------------ #
#  路由 1：POST /api/consultation/start                                 #
# ------------------------------------------------------------------ #

@app.post("/api/consultation/start", summary="开始一次新问诊")
def start_consultation(req: StartRequest, db: Session = Depends(get_db)):
    """
    创建问诊记录，初始化预算。
    前端收到 record_id 后，所有后续操作均携带此 ID。
    """
    # 校验病例和用户是否存在（按字符串代码查找）
    case = db.query(Case).filter(Case.tencent_kb_id == req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"病例代码={req.case_id} 不存在")

    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"用户 ID={req.user_id} 不存在")

    # 创建问诊记录（case_id 必须存整数 PK，不能存字符串代码）
    record = ConsultationRecord(
        user_id=req.user_id,
        case_id=case.id,       # ← 使用 Case 整数主键，而非字符串代码
        status="ongoing",
        budget_left=case.initial_budget,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 兜底题目：当 DB 中的 standard_answer 尚未包含 questions 时使用
    _FALLBACK_QUESTIONS = [
        "1. 该患者最可能的初步诊断是什么？请写出疾病全称。",
        "2. 对于该患者，哪些器械检查是诊断所必须完成的（至少列出 3 项）？",
        "3. 根据检查结果，该患者存在哪些合并症或并发症风险？",
    ]
    questions = case.standard_answer.get("questions") or _FALLBACK_QUESTIONS

    return {
        "record_id": record.id,
        "budget_left": record.budget_left,
        "case_info": {
            "id": case.id,
            "title": case.title,
            # 考核任务题目可向前端展示；patient_prompt / standard_answer / standard_answers 不暴露
            "questions": questions,
        },
        "message": "问诊已开始，请向患者问诊",
    }


# ------------------------------------------------------------------ #
#  路由 2：POST /api/consultation/chat                                  #
# ------------------------------------------------------------------ #

@app.post("/api/consultation/chat", summary="发送问诊消息（SSE 流式响应）")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """
    接收医生消息，调用腾讯云 LKE 流式接口，以 SSE 格式将 AI 患者的回复实时推送给前端。

    SSE 数据格式（每行）：
      data: {"content": "文字片段"}\n\n
    结束标记：
      data: [DONE]\n\n
    """
    # 校验记录状态
    record = _get_active_record(req.record_id, db)
    case = db.query(Case).filter(Case.id == record.case_id).first()

    # 立即持久化用户消息（防止流式过程中连接中断丢失记录）
    user_msg = DialogueMessage(
        record_id=req.record_id,
        role="user",
        content=req.doctor_message,
    )
    db.add(user_msg)
    db.commit()

    # 从病例元数据中取出知识库检索词，构建 RAG 患者人设
    # （告知 LKE 去知识库中检索哪个患者档案，由云端 RAG 完成角色填充）
    kb_query = case.standard_answer.get("kb_query", "") if case else ""
    patient_role = ai_client.build_patient_role(kb_query)

    full_user_message = req.doctor_message

    async def generate():
        """异步生成器：流式 yield SSE 数据，结束后将完整回复入库"""
        accumulated: list[str] = []

        try:
            async for chunk in ai_client.stream_chat(
                session_id=str(req.record_id),
                doctor_message=full_user_message,
                system_role=patient_role,
            ):
                # ── 探头⑥：确认 generate() 层收到了 chunk ─────────────────
                print(f"【探头⑥ generate收到chunk】 {chunk!r}")
                accumulated.append(chunk)
                sse_data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"data: {sse_data}\n\n"

        except RuntimeError as e:
            # AI 服务异常时推送错误事件，不中断 SSE 连接
            print(f"\033[91m【探头⑥ RuntimeError】 {e}\033[0m")
            error_msg = f"AI 服务暂时不可用：{str(e)[:100]}"
            accumulated.append(error_msg)
            yield f"data: {json.dumps({'content': error_msg, 'error': True}, ensure_ascii=False)}\n\n"

        finally:
            # ── 探头⑦：accumulated 汇总 ────────────────────────────────────
            if not accumulated:
                print("\033[91m【探头⑦ 警告】accumulated 为空！stream_chat 未 yield 任何内容\033[0m")
            else:
                print(f"【探头⑦ 汇总】共收到 {len(accumulated)} 个 chunk，总字数 {sum(len(c) for c in accumulated)}")

            # 无论是否发生异常，只要有内容就入库
            if accumulated:
                full_content = "".join(accumulated)
                # 使用新的 DB 会话（原 session 可能已被 FastAPI 关闭）
                save_db = SessionLocal()
                try:
                    assistant_msg = DialogueMessage(
                        record_id=req.record_id,
                        role="assistant",
                        content=full_content,
                    )
                    save_db.add(assistant_msg)
                    save_db.commit()
                finally:
                    save_db.close()

            # 发送结束标记
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲，保证实时推送
        },
    )


# ------------------------------------------------------------------ #
#  路由 3：POST /api/consultation/instrument                            #
# ------------------------------------------------------------------ #

@app.post("/api/consultation/instrument", summary="使用诊察器械/检查项目")
async def use_instrument(req: InstrumentRequest, db: Session = Depends(get_db)):
    """
    扣减金币，调用知识库实时提取检查数值，记录检查日志并返回结果。

    业务规则：
    - 若金币不足，返回 400 错误
    - 优先通过 AI 从知识库提取该案例的真实检查数值
    - 同一检查可重复使用，但每次均消耗金币
    """
    record = _get_active_record(req.record_id, db)

    # 获取检查费用（未知器械收取默认费用 50 金币）
    cost = INSTRUMENT_COSTS.get(req.action_name, 50)

    # ── 预算校验 ──
    if record.budget_left < cost:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f'金币不足！"{req.action_name}"需要 {cost} 金币，'
                f'当前余额 {record.budget_left} 金币'
            ),
        )

    # ── 查询病例元数据 ──
    case = db.query(Case).filter(Case.id == record.case_id).first()
    standard_answer = (case.standard_answer or {}) if case else {}
    kb_query = standard_answer.get("kb_query", "")
    static_results: dict = standard_answer.get("instrument_results", {})

    if req.action_name in static_results:
        # 优先返回本地静态数据（即时响应，无 AI 延迟）
        result_text = static_results[req.action_name]
    else:
        # 该病例档案中未收录此检查项，提示无需检查
        result_text = "无需该项检查"

    # ── 原子操作：扣减预算 + 写入日志 ──
    record.budget_left -= cost
    log = InstrumentLog(
        record_id=req.record_id,
        action_name=req.action_name,
        result_text=result_text,
        cost=cost,
    )
    db.add(log)
    db.commit()
    db.refresh(record)

    return {
        "action_name": req.action_name,
        "result": result_text,
        "cost": cost,
        "budget_left": record.budget_left,
    }


# ------------------------------------------------------------------ #
#  路由 4：POST /api/consultation/submit                                #
# ------------------------------------------------------------------ #

@app.post("/api/consultation/submit", summary="提交最终诊断并获取 AI 评分")
async def submit_consultation(req: SubmitRequest, db: Session = Depends(get_db)):
    """
    聚合全部对话记录和器械日志，调用 AI 评分服务，
    将状态更新为 completed 并返回评分结果。
    """
    record = _get_active_record(req.record_id, db)

    # 通过 record 的整数外键查找 Case（start_consultation 已保证存的是 case.id）
    case = db.query(Case).filter(Case.id == record.case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到对应病例数据（case_id={record.case_id}），请重新开始问诊",
        )

    # ── 聚合器械检查记录（仅血压 / 血糖参与评分） ──
    logs = (
        db.query(InstrumentLog)
        .filter(InstrumentLog.record_id == req.record_id)
        .order_by(InstrumentLog.id)
        .all()
    )
    _GRADED_INSTRUMENTS = {"血压测量", "血糖检测"}
    exam_instrument_lines = [
        f"- {log.action_name}：{log.result_text}"
        for log in logs
        if log.action_name in _GRADED_INSTRUMENTS
    ]
    exam_instruments_text = (
        "\n".join(exam_instrument_lines) if exam_instrument_lines
        else "（考生未进行血压或血糖检查）"
    )

    # ── 汇总评分材料（精简版：仅考官必需信息） ──
    budget_spent = case.initial_budget - record.budget_left
    spend_pct = round(budget_spent * 100 / case.initial_budget) if case.initial_budget else 0

    # 从 standard_answer JSON 读取题目和官方标答
    std = case.standard_answer or {}
    raw_questions = std.get("questions") or []
    questions_text = "\n".join(
        f"{i+1}. {q}" for i, q in enumerate(raw_questions)
    ) if raw_questions else "（本关暂无结构化考核题目）"
    standard_answers_text = std.get("standard_answers", "").strip() or "（本关暂无结构化标准答案）"

    # req.final_diagnosis 在新版前端已是组装好的结构化作答字符串
    player_answers_text = req.final_diagnosis.strip() if req.final_diagnosis else "（考生未作答）"

    aggregated_data = (
        f"【本关考核问题】\n{questions_text}\n\n"
        f"【官方标准答案】\n{standard_answers_text}\n\n"
        f"【考生实际作答】\n{player_answers_text}\n\n"
        f"【血压 / 血糖检查结果】\n{exam_instruments_text}\n\n"
        f"【金币消耗】初始预算 {case.initial_budget} 金币，"
        f"实际花费 {budget_spent} 金币（占比 {spend_pct}%），"
        f"剩余 {record.budget_left} 金币。"
    )

    # ── 调用 AI 评分（使用 kb_query 让 LKE 从知识库检索标准答案后评分）──
    kb_query = case.standard_answer.get("kb_query", case.title) if case else ""
    evaluation: dict = await ai_client.evaluate_doctor(
        aggregated_data=aggregated_data,
        kb_query=kb_query,
    )

    score: float = float(evaluation.get("score", 60))
    eval_text: str = evaluation.get("evaluation", "")

    # ── 更新记录为已完成 ──
    record.status = "completed"
    record.final_score = score
    record.ai_evaluation = evaluation
    record.final_diagnosis = req.final_diagnosis
    record.completed_at = datetime.utcnow()

    # 同步更新用户累计总分
    user = db.query(User).filter(User.id == record.user_id).first()
    if user:
        user.total_score = (user.total_score or 0.0) + score

    db.commit()

    return {
        "record_id": req.record_id,
        "final_score": score,
        "evaluation": eval_text,
        "instruments_used": len(logs),
        "budget_spent": case.initial_budget - record.budget_left,
        "instruments_checked": [log.action_name for log in logs],
        # 官方标准答案（供考后复盘，不含内部 instrument_results 原始数据）
        "standard_answer_public": {
            "diagnosis": case.standard_answer.get("diagnosis", ""),
            "required_instruments": case.standard_answer.get("required_instruments", []),
            "key_findings": case.standard_answer.get("standard_answers", {}),
        },
        "message": "问诊已完成，评分已生成",
    }


# ------------------------------------------------------------------ #
#  健康检查                                                             #
# ------------------------------------------------------------------ #

@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok", "service": "SmartDiag API"}
