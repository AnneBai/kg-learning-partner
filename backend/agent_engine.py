"""
知识图谱学习伙伴 - Agent 引擎
封装 smolagents.CodeAgent 的初始化与调用
支持多模型提供商：HuggingFace / OpenAI兼容(Kimi等) / LiteLLM
提供提示词构建和 JSON 解析工具
"""

import os
import re
import json
import logging

logger = logging.getLogger(__name__)

# ==================== smolagents 导入 ====================

try:
    from smolagents import CodeAgent, WebSearchTool
    from smolagents import utils as smolagents_utils
    from smolagents import agents as smolagents_agents
except ImportError:
    raise ImportError(
        'smolagents 未安装。请运行：pip install "smolagents[toolkit]"'
    )

# 按需导入模型类（避免未使用的依赖报错）
_MODEL_CLASSES = {}
_CODE_PARSING_PATCHED = False


def _patch_parse_code_blobs() -> None:
    """
    扩展 smolagents 的代码解析：当模型直接输出 JSON/文本（未包在 <code> 中）时，
    自动转换为 final_answer(...) 调用，避免反复解析失败重试。
    """
    global _CODE_PARSING_PATCHED
    if _CODE_PARSING_PATCHED:
        return

    original = smolagents_utils.parse_code_blobs

    def _parse_with_fallback(text: str, code_block_tags: tuple[str, str]) -> str:
        try:
            return original(text, code_block_tags)
        except ValueError:
            cleaned = text.strip()
            closing_tag = code_block_tags[1]
            if closing_tag and cleaned.endswith(closing_tag):
                cleaned = cleaned[: -len(closing_tag)].strip()

            if cleaned.startswith("{"):
                data = extract_json(cleaned)
                return f"final_answer({json.dumps(data, ensure_ascii=False)})"

            if cleaned and not cleaned.startswith(code_block_tags[0]):
                return f"final_answer({json.dumps(cleaned, ensure_ascii=False)})"

            raise

    smolagents_utils.parse_code_blobs = _parse_with_fallback
    smolagents_agents.parse_code_blobs = _parse_with_fallback
    _CODE_PARSING_PATCHED = True


def _get_model_class(name: str):
    """延迟导入模型类"""
    if name not in _MODEL_CLASSES:
        if name == "InferenceClientModel":
            from smolagents import InferenceClientModel
            _MODEL_CLASSES[name] = InferenceClientModel
        elif name == "OpenAIServerModel":
            from smolagents import OpenAIServerModel
            _MODEL_CLASSES[name] = OpenAIServerModel
        elif name == "LiteLLMModel":
            from smolagents import LiteLLMModel
            _MODEL_CLASSES[name] = LiteLLMModel
    return _MODEL_CLASSES[name]


# ==================== 流式兼容模型包装器 ====================

def _make_streaming_model(base_model_instance):
    """
    返回一个代理对象，将 generate() 方法替换为流式实现。

    部分 OpenAI 兼容代理（如内部转发代理）只支持 SSE 流式响应，
    非流式请求会返回原始 SSE 文本字符串，导致 response.choices 报错。
    该包装器通过 stream=True 采集完整内容，再组装为 ChatMessage。
    """
    from smolagents.models import ChatMessage, TokenUsage

    original_generate = base_model_instance.generate

    def _streaming_generate(messages, stop_sequences=None, response_format=None,
                             tools_to_call_from=None, **kwargs):
        # 先尝试原始非流式调用
        try:
            result = original_generate(
                messages=messages,
                stop_sequences=stop_sequences,
                response_format=response_format,
                tools_to_call_from=tools_to_call_from,
                **kwargs,
            )
            # 如果 result 是字符串，说明代理返回了原始 SSE 文本，需要改用流式
            if isinstance(result, str):
                raise ValueError("non-streaming proxy returned raw SSE string")
            return result
        except (AttributeError, ValueError, TypeError):
            pass

        # 回退：使用流式请求采集完整响应
        logger.info("使用流式模式采集模型响应（代理仅支持 SSE）")
        completion_kwargs = base_model_instance._prepare_completion_kwargs(
            messages=messages,
            stop_sequences=stop_sequences,
            response_format=response_format,
            tools_to_call_from=tools_to_call_from,
            model=base_model_instance.model_id,
            custom_role_conversions=base_model_instance.custom_role_conversions,
            convert_images_to_image_urls=True,
            **kwargs,
        )

        content_parts = []
        input_tokens = 0
        output_tokens = 0

        for chunk in base_model_instance.client.chat.completions.create(
            **completion_kwargs,
            stream=True,
            stream_options={"include_usage": True},
        ):
            if chunk.usage:
                input_tokens = chunk.usage.prompt_tokens or 0
                output_tokens = chunk.usage.completion_tokens or 0
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    content_parts.append(delta.content)

        full_content = "".join(content_parts)

        if stop_sequences and not base_model_instance.supports_stop_parameter:
            from smolagents.models import remove_content_after_stop_sequences
            full_content = remove_content_after_stop_sequences(full_content, stop_sequences)

        return ChatMessage(
            role="assistant",
            content=full_content,
            tool_calls=None,
            raw=None,
            token_usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )

    base_model_instance.generate = _streaming_generate
    return base_model_instance


# ==================== 配置常量 ====================

# 模型提供商，支持：huggingface / openai / litellm
MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "huggingface").lower().strip()

# 默认模型 ID（各提供商不同）
_DEFAULT_MODEL_IDS = {
    "huggingface": "Qwen/Qwen3-Next-80B-A3B-Thinking",
    "openai": "gpt-4o",
    "litellm": "gpt-4o",
}

# 各提供商所需的 Python extras
_REQUIRED_EXTRAS = {
    "huggingface": "toolkit",
    "openai": "openai",
    "litellm": "litellm",
}


def _resolve_model_id() -> str:
    """解析模型 ID，优先级：MODEL_ID > 提供商默认值"""
    return os.environ.get("MODEL_ID") or os.environ.get("HF_MODEL_ID") or _DEFAULT_MODEL_IDS.get(MODEL_PROVIDER, "gpt-4o")


def _create_model():
    """
    根据 MODEL_PROVIDER 环境变量创建对应的模型实例

    Returns:
        smolagents Model 实例

    Raises:
        ImportError: 缺少所需 extras 依赖时
        ValueError: 配置不正确时
    """
    model_id = _resolve_model_id()

    logger.info(f"使用模型提供商: {MODEL_PROVIDER}, 模型ID: {model_id}")

    # ---------- Hugging Face ----------
    if MODEL_PROVIDER == "huggingface":
        ModelClass = _get_model_class("InferenceClientModel")

        token = os.environ.get("HF_TOKEN")
        if not token:
            raise ValueError(
                "使用 HuggingFace 模型需要设置 HF_TOKEN 环境变量。\n"
                "获取地址：https://huggingface.co/settings/tokens"
            )

        return ModelClass(
            model_id=model_id,
            token=token,
        )

    # ---------- OpenAI 兼容（Kimi、OpenRouter、Together 等） ----------
    elif MODEL_PROVIDER == "openai":
        ModelClass = _get_model_class("OpenAIServerModel")

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "使用 OpenAI 兼容 API 需要设置 OPENAI_API_KEY 环境变量。\n"
                "Kimi: https://platform.moonshot.cn/console/api-keys \n"
                "OpenAI: https://platform.openai.com/api-keys"
            )

        kwargs = {
            "model_id": model_id,
            "api_key": api_key,
        }

        # 自定义 base URL（如 Kimi、OpenRouter）
        base_url = os.environ.get("OPENAI_BASE_URL")
        if base_url:
            kwargs["api_base"] = base_url

        model_instance = ModelClass(**kwargs)

        # 部分代理（如内部转发代理）只返回 SSE 流式响应，需要流式兼容包装
        return _make_streaming_model(model_instance)

    # ---------- LiteLLM（100+ 提供商） ----------
    elif MODEL_PROVIDER == "litellm":
        ModelClass = _get_model_class("LiteLLMModel")

        api_key = os.environ.get("LITELLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "使用 LiteLLM 需要设置 LITELLM_API_KEY 或 OPENAI_API_KEY 环境变量"
            )

        kwargs = {
            "model_id": model_id,
            "api_key": api_key,
        }

        base_url = os.environ.get("LITELLM_API_BASE") or os.environ.get("OPENAI_BASE_URL")
        if base_url:
            kwargs["api_base"] = base_url

        return ModelClass(**kwargs)

    else:
        raise ValueError(
            f"不支持的模型提供商: {MODEL_PROVIDER}\n"
            f"支持的值: huggingface / openai / litellm"
        )


def create_agent():
    """
    创建并返回配置好的 CodeAgent 实例

    自动根据环境变量选择模型提供商，支持：
    - huggingface: Hugging Face Inference API（默认）
    - openai: OpenAI 兼容 API（Kimi、OpenRouter、Together、vLLM 等）
    - litellm: LiteLLM 网关（100+ 提供商）

    环境变量：
        MODEL_PROVIDER: 模型提供商（默认 huggingface）
        MODEL_ID: 模型 ID
        HF_TOKEN: HuggingFace Token
        OPENAI_API_KEY: OpenAI 兼容 API Key
        OPENAI_BASE_URL: 自定义 API 基础地址（Kimi 等需要）

    Returns:
        配置好的 CodeAgent 实例
    """
    try:
        model = _create_model()
    except ImportError as e:
        extra = _REQUIRED_EXTRAS.get(MODEL_PROVIDER, "toolkit")
        raise ImportError(
            f"{e}\n\n"
            f'请运行：pip install "smolagents[{extra}]"'
        )

    _patch_parse_code_blobs()

    agent = CodeAgent(
        tools=[WebSearchTool()],
        model=model,
        additional_authorized_imports=["json"],
        max_steps=12,
    )

    return agent


# ==================== Agent 运行封装 ====================

_CODE_AGENT_FORMAT = """
【输出格式 - 必须严格遵守】
1. 先用一行 `Thoughts: ...` 简述思路
2. 再用 <code>...</code> 包裹 Python 代码，通过 final_answer() 提交结果
3. 禁止直接输出 JSON 或 Markdown 代码块

图谱任务示例：
Thoughts: 搜索完成，提交图谱数据
<code>
final_answer({
    "nodes": [{"id": "example", "label": "示例", "category": "核心概念", "description": "描述"}],
    "edges": []
})
</code>

对话任务示例：
Thoughts: 已整理好回答
<code>
final_answer("你的回答正文")
</code>
"""


def _scan_memory_for_json(agent) -> dict | None:
    """从 Agent 记忆中扫描最近的有效图谱 JSON"""
    for step in reversed(agent.memory.steps):
        for attr in ("action_output", "model_output"):
            value = getattr(step, attr, None)
            if isinstance(value, dict) and value.get("nodes") is not None:
                return value
            if isinstance(value, str) and value.strip():
                try:
                    data = extract_json(value)
                    if data.get("nodes") is not None:
                        return data
                except ValueError:
                    continue
    return None


def run_agent_json(agent, prompt: str) -> dict:
    """运行 Agent 并返回图谱 JSON（nodes + edges）"""
    _patch_parse_code_blobs()
    result = agent.run(prompt)

    if isinstance(result, dict) and result.get("nodes") is not None:
        return result
    if isinstance(result, str):
        return extract_json(result)

    cached = _scan_memory_for_json(agent)
    if cached:
        return cached

    raise ValueError(f"Agent 未返回有效图谱 JSON，结果类型: {type(result)}")


def run_agent_text(agent, prompt: str) -> str:
    """运行 Agent 并返回纯文本回答"""
    _patch_parse_code_blobs()
    result = agent.run(prompt)

    if isinstance(result, str) and result.strip():
        return result.strip()
    if result is not None:
        return str(result)

    raise ValueError("Agent 未返回有效文本回答")


# ==================== JSON 解析工具 ====================

def extract_json(text: str) -> dict:
    """
    从 Agent 返回的文本中提取 JSON 对象

    提取策略：
    1. 先尝试提取 Markdown 代码块中的 JSON
    2. 再尝试提取最外层 {} 包裹的 JSON
    3. 都失败时抛出 ValueError

    Args:
        text: Agent 返回的原始文本

    Returns:
        解析后的 JSON 字典

    Raises:
        ValueError: 无法提取有效 JSON 时
    """
    if not text or not text.strip():
        raise ValueError("输入文本为空")

    # 策略 1：提取 Markdown 代码块
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    matches = re.findall(code_block_pattern, text, re.DOTALL)

    for match in matches:
        match = match.strip()
        if match:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

    # 策略 2：提取最外层 {} 包裹的内容
    json_pattern = r"(\{[\s\S]*\})"
    matches = re.findall(json_pattern, text)

    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            # 尝试修复常见格式问题后再解析
            try:
                # 去除尾部逗号
                fixed = re.sub(r",(\s*[}\]])", r"\1", match)
                return json.loads(fixed)
            except json.JSONDecodeError:
                continue

    raise ValueError(f"无法从文本中提取有效 JSON。原文：{text[:500]}")


# ==================== 提示词构建 ====================

def build_graph_prompt(topic: str) -> str:
    """
    构建初始图谱生成的 Agent 提示词

    Args:
        topic: 用户输入的学习主题

    Returns:
        完整的提示词字符串
    """
    return f"""你是一个知识图谱构建专家。请搜索并深入理解主题"{topic}"，然后生成一个结构化的知识图谱。

要求：
1. 先使用 WebSearchTool 搜索该主题的核心知识点
2. 搜索完成后，用 final_answer() 提交包含 nodes 和 edges 的字典
3. 节点数量：8-12 个核心知识点
4. 每个节点必须包含：
   - id: 英文驼峰命名（如 machineLearning）
   - label: 中文名称
   - category: 必须是以下四选一：核心概念 / 底层原理 / 关联工具 / 实践案例
   - description: 50字以内的中文描述
5. 每条边必须包含：
   - id: 英文驼峰（如 mlToDL）
   - source: 源节点 id
   - target: 目标节点 id
   - relation: 中文动词（如"包含"、"应用于"、"依赖于"）
   - strength: 1-10 的整数，表示关联强度

JSON 数据结构示例：
{{
  "nodes": [
    {{
      "id": "machineLearning",
      "label": "机器学习",
      "category": "核心概念",
      "description": "让计算机从数据中学习规律的算法集合"
    }}
  ],
  "edges": [
    {{
      "id": "mlToDL",
      "source": "machineLearning",
      "target": "deepLearning",
      "relation": "包含",
      "strength": 9
    }}
  ]
}}

主题：{topic}
{_CODE_AGENT_FORMAT}"""


def build_expand_prompt(
    node_id: str,
    node_label: str,
    category: str,
    existing_ids: list[str]
) -> str:
    """
    构建节点展开探索的 Agent 提示词

    Args:
        node_id: 当前节点 ID
        node_label: 当前节点中文名称
        category: 当前节点分类
        existing_ids: 图谱中已有节点 ID 列表（用于去重）

    Returns:
        完整的提示词字符串
    """
    existing_ids_str = ", ".join(existing_ids) if existing_ids else "无"

    return f"""你是一个知识图谱构建专家。请围绕"{node_label}"（category: {category}）展开深入探索。

要求：
1. 先使用 WebSearchTool 搜索"{node_label}"的深入知识
2. 搜索完成后，用 final_answer() 提交包含 nodes 和 edges 的字典
3. 生成 4-6 个与"{node_label}"直接关联的新知识点
4. 每个新节点必须包含：
   - id: 英文驼峰命名（必须全局唯一）
   - label: 中文名称
   - category: 必须是以下四选一：核心概念 / 底层原理 / 关联工具 / 实践案例
   - description: 50字以内的中文描述
5. 每条新边必须包含：
   - id: 英文驼峰（全局唯一）
   - source: "{node_id}"（当前展开节点）
   - target: 新节点 id
   - relation: 中文动词
   - strength: 1-10 的整数

严禁重复！已有节点 ID 列表：{existing_ids_str}
新节点的 id 绝不能与上述任何 ID 重复。

JSON 数据结构：
{{
  "nodes": [{{"id": "...", "label": "...", "category": "...", "description": "..."}}],
  "edges": [{{"id": "...", "source": "{node_id}", "target": "...", "relation": "...", "strength": 8}}]
}}
{_CODE_AGENT_FORMAT}"""


def build_chat_prompt(
    question: str,
    graph_context: str,
    history: list[dict],
    selected_node: str | None
) -> str:
    """
    构建基于图谱上下文的对话 Agent 提示词

    Args:
        question: 用户问题
        graph_context: 当前图谱的 JSON 字符串
        history: 最近对话记录列表
        selected_node: 当前选中节点名称（可选）

    Returns:
        完整的提示词字符串
    """
    history_str = ""
    if history:
        # 只取最近 6 条对话作为上下文
        for msg in history[-6:]:
            role = "用户" if msg["role"] == "user" else "助手"
            history_str += f"{role}: {msg['content']}\n"

    node_context = f"\n当前选中节点：{selected_node}" if selected_node else ""

    return f"""你是一个知识图谱学习助手。请基于以下知识图谱上下文回答用户问题。

当前知识图谱：
{graph_context}
{node_context}

最近对话记录：
{history_str}

用户问题：{question}

回答要求：
1. 优先引用图谱中的相关节点，用【节点名】标记引用
2. 回答要准确、简洁、有深度
3. 如果图谱中未覆盖用户问题的内容，明确说"建议展开【xxx】节点"来引导用户探索
4. 如果选中节点与问题相关，优先围绕该节点展开回答
5. 用 final_answer() 提交你的回答文本
{_CODE_AGENT_FORMAT}"""
