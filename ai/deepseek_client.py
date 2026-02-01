"""
FundPilot-AI DeepSeek API 客户端
使用 OpenAI 兼容接口调用 DeepSeek 模型
"""

from typing import Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import get_config
from core.logger import get_logger

logger = get_logger("deepseek_client")

# 请求超时（秒）
REQUEST_TIMEOUT = 60


class DeepSeekClient:
    """DeepSeek API 客户端"""
    
    def __init__(self):
        config = get_config()
        self.model = config.deepseek.model
        self.client = OpenAI(
            api_key=config.deepseek.api_key,
            base_url=config.deepseek.base_url
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> Optional[str]:
        """
        发送聊天请求
        
        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            temperature: 温度参数
            max_tokens: 最大返回 token
        
        Returns:
            AI 回复内容，失败返回 None
        """
        try:
            logger.info("调用 DeepSeek API...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=REQUEST_TIMEOUT
            )
            
            # 安全获取内容
            if not response.choices:
                logger.warning("DeepSeek 返回无 choices")
                return None
                
            content = response.choices[0].message.content
            
            # 处理空内容情况
            if not content or not content.strip():
                logger.warning(f"DeepSeek 返回内容为空 (finish_reason: {response.choices[0].finish_reason})")
                return None
            
            # 记录返回内容（截断显示）
            display_content = content[:100] + "..." if len(content) > 100 else content
            logger.info(f"DeepSeek 返回: {display_content}")
            return content
            
        except Exception as e:
            logger.error(f"DeepSeek API 调用失败: {e}")
            raise
    
    def get_decision(self, system_prompt: str, context_json: str) -> Optional[str]:
        """
        获取投资决策
        
        Args:
            system_prompt: 系统提示词
            context_json: JSON 格式的上下文
        
        Returns:
            AI 决策回复
        """
        user_message = f"""请基于以下数据给出投资决策建议：

```json
{context_json}
```

请严格按照以下格式回复：
1. 【决策】：[双倍补仓/正常定投/暂停定投/观望] 之一
2. 【理由】：简短说明（50字以内）
"""
        
        try:
            return self.chat(system_prompt, user_message)
        except Exception as e:
            logger.error(f"获取决策失败: {e}")
            return None


# 全局客户端实例（延迟加载）
_client: Optional[DeepSeekClient] = None


def get_deepseek_client() -> DeepSeekClient:
    """获取 DeepSeek 客户端单例"""
    global _client
    if _client is None:
        _client = DeepSeekClient()
    return _client
