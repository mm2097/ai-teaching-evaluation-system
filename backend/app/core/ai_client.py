"""算法服务（AI 服务，默认 8001）统一调用约定。

历史上后端有 5 处对 8001 的调用各自硬编码地址与互不一致的超时
（30s/60s/90s/180s），且普遍小于算法侧单次 LLM 调用的最坏耗时，导致：
- 报告 LLM 增强几乎必超时回退模板（token 照烧）
- 简答题 AI 判分高频超时，学生答案落「0 分待人工」
- Agent 组卷工具必超时

所有对算法服务的调用统一从本模块取地址，超时取 ``settings.AI_*_TIMEOUT``
（调用点在请求时读取，便于测试替换与运维调参）。

超时不变量与各端点约定见 ``app/core/config.py`` 的 AI_*_TIMEOUT 注释；
算法侧各端点的调用次数约定见 ``algorithm/src``（judge/reporter/agent 为
单次调用不重试，generator 允许完整重试链）。
"""
from app.core.config import settings


def ai_base_url() -> str:
    """算法服务基础地址（AI_SERVICE_HOST / AI_SERVICE_PORT 可配）。"""
    return f"http://{settings.AI_SERVICE_HOST}:{settings.AI_SERVICE_PORT}"
