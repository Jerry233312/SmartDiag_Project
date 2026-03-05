# -*- coding: utf-8 -*-
"""
models.py — SQLAlchemy ORM 模型定义
包含 5 张核心表：User / Case / ConsultationRecord / DialogueMessage / InstrumentLog
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    """
    用户表：存储平台学员信息。
    password_hash 存储经过哈希处理的密码，严禁存储明文。
    """
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username: str = Column(String(50), unique=True, nullable=False, index=True, comment="登录用户名")
    password_hash: str = Column(String(255), nullable=False, comment="bcrypt 哈希密码")
    total_score: float = Column(Float, default=0.0, comment="累计总分")
    created_at: datetime = Column(DateTime, server_default=func.now(), comment="注册时间")

    # 关联关系
    records: list = relationship("ConsultationRecord", back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username}>"


class Case(Base):
    """
    病例表：存储结构化病例数据。
    - patient_prompt: 给 AI 的人设 Prompt，定义患者角色
    - tencent_kb_id: 对应腾讯云 LKE 的 BOT_APP_KEY 或知识库 ID
    - standard_answer: JSON，包含必查器械列表/标准诊断/各检查结果
    """
    __tablename__ = "cases"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title: str = Column(String(200), nullable=False, comment="病例标题")
    patient_prompt: str = Column(Text, nullable=False, comment="AI 患者人设 Prompt")
    tencent_kb_id: str = Column(String(200), nullable=False, comment="腾讯云 BotID 或知识库 ID")
    standard_answer: dict = Column(
        JSON,
        nullable=False,
        comment="""标准答案 JSON，格式示例：
        {
            "required_instruments": ["血糖检测", "尿常规"],
            "diagnosis": "2型糖尿病",
            "instrument_results": {
                "血糖检测": "空腹血糖 9.2mmol/L...",
                "听诊": "心音正常..."
            }
        }
        """,
    )
    initial_budget: int = Column(Integer, default=1000, comment="初始诊查预算（金币）")

    records: list = relationship("ConsultationRecord", back_populates="case")

    def __repr__(self) -> str:
        return f"<Case id={self.id} title={self.title}>"


class ConsultationRecord(Base):
    """
    问诊记录表：记录一次完整的问诊会话。
    - status: ongoing（进行中）| completed（已提交评分）
    - budget_left: 实时剩余金币，由后端扣减，前端只读
    - ai_evaluation: 提交后 AI 返回的 JSON 评分结果
    """
    __tablename__ = "consultation_records"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    case_id: int = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    status: str = Column(
        String(20), default="ongoing", nullable=False, comment="ongoing | completed"
    )
    budget_left: int = Column(Integer, nullable=False, comment="剩余诊查金币")
    final_score: Optional[float] = Column(Float, nullable=True, comment="最终得分（0~100）")
    ai_evaluation: Optional[dict] = Column(JSON, nullable=True, comment="AI 评语 JSON")
    final_diagnosis: Optional[str] = Column(Text, nullable=True, comment="医生提交的最终诊断")
    created_at: datetime = Column(DateTime, server_default=func.now())
    completed_at: Optional[datetime] = Column(DateTime, nullable=True)

    # 关联关系，便于 ORM 级联查询
    user = relationship("User", back_populates="records")
    case = relationship("Case", back_populates="records")
    messages: list = relationship(
        "DialogueMessage", back_populates="record", order_by="DialogueMessage.id"
    )
    instrument_logs: list = relationship(
        "InstrumentLog", back_populates="record", order_by="InstrumentLog.id"
    )

    def __repr__(self) -> str:
        return f"<ConsultationRecord id={self.id} status={self.status}>"


class DialogueMessage(Base):
    """
    对话消息表：记录医患对话的每一条消息。
    - role: user（医生）| assistant（AI 患者）
    """
    __tablename__ = "dialogue_messages"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    record_id: int = Column(
        Integer, ForeignKey("consultation_records.id"), nullable=False, index=True
    )
    role: str = Column(String(20), nullable=False, comment="user | assistant")
    content: str = Column(Text, nullable=False, comment="消息正文")
    created_at: datetime = Column(DateTime, server_default=func.now())

    record = relationship("ConsultationRecord", back_populates="messages")

    def __repr__(self) -> str:
        return f"<DialogueMessage id={self.id} role={self.role}>"


class InstrumentLog(Base):
    """
    器械检查日志表：记录每次使用诊察工具的详情。
    - action_name: 如 "听诊" / "血常规"
    - result_text: 该检查的模拟结果（来自病例 standard_answer）
    - cost: 本次操作消耗的金币数
    """
    __tablename__ = "instrument_logs"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    record_id: int = Column(
        Integer, ForeignKey("consultation_records.id"), nullable=False, index=True
    )
    action_name: str = Column(String(100), nullable=False, comment="检查项目名称")
    result_text: str = Column(Text, nullable=False, comment="检查结果描述")
    cost: int = Column(Integer, nullable=False, comment="消耗金币数")
    created_at: datetime = Column(DateTime, server_default=func.now())

    record = relationship("ConsultationRecord", back_populates="instrument_logs")

    def __repr__(self) -> str:
        return f"<InstrumentLog id={self.id} action={self.action_name}>"
