from typing import List, Dict
from dataclasses import dataclass, field

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float

@dataclass
class AgentCostLog:
    agent_type: str
    action: str
    conversation_id: str
    token_usage: TokenUsage

@dataclass
class CostTracker:
    logs: List[AgentCostLog] = field(default_factory=list)

    def log_cost(
        self,
        agent_type: str,
        action: str,
        conversation_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "gpt-4"
    ) -> None:
        total_tokens = prompt_tokens + completion_tokens
        cost = self._calculate_cost(prompt_tokens, completion_tokens, model)
        usage = TokenUsage(prompt_tokens, completion_tokens, total_tokens, cost)
        log = AgentCostLog(agent_type, action, conversation_id, usage)
        self.logs.append(log)

    def _calculate_cost(self, prompt: int, completion: int, model: str) -> float:
        # Adjust prices based on OpenAI pricing
        if model == "gpt-4":
            return (prompt / 1000) * 0.03 + (completion / 1000) * 0.06
        elif model == "gpt-3.5-turbo":
            return (prompt / 1000) * 0.0015 + (completion / 1000) * 0.002
        return 0.0

    def total_cost(self) -> float:
        return sum(log.token_usage.cost for log in self.logs)

    def summary(self) -> List[Dict]:
        return [
            {
                "agent": log.agent_type,
                "action": log.action,
                "conversation_id": log.conversation_id,
                "tokens": log.token_usage.total_tokens,
                "cost_SEK": round(log.token_usage.cost * 10.9, 3)  # USD to SEK
            }
            for log in self.logs
        ]

# Global instance for reuse
cost_tracker = CostTracker()
