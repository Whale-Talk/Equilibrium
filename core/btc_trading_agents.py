import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from typing import Dict, Any, Optional
from openai import OpenAI
import pandas as pd
from config import Config


class BTCRadingAgents:
    """基于TradingAgents架构的BTC交易系统"""
    
    def __init__(self, config: type = Config):
        self.config = config
        self.client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL + "/v1"
        )
    
    def _call_llm(self, system_prompt: str, user_prompt: str, need_json: bool = False) -> str:
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM调用错误: {e}")
            return ""
    
    def _parse_json(self, text: str) -> Dict:
        try:
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except:
            return {}
    
    def run_analysis(self, price: float, indicators: Dict, news: str = "") -> Dict:
        """运行完整的TradingAgents分析流程"""
        
        # 1. 技术分析师
        tech_report = self._technical_analyst(price, indicators)
        
        # 2. 新闻分析师
        news_report = self._news_analyst(news)
        
        # 3. 多头研究员
        bullish_arg = self._bullish_researcher(tech_report, news_report)
        
        # 4. 空头研究员
        bearish_arg = self._bearish_researcher(tech_report, news_report)
        
        # 5. 交易员决策
        trader_decision = self._trader(price, tech_report, news_report, bullish_arg, bearish_arg)
        
        # 6. 风控经理审核
        risk_result = self._risk_manager(trader_decision, price)
        
        return {
            "action": risk_result.get("action", trader_decision.get("action")),
            "confidence": trader_decision.get("confidence", 0),
            "position_size": trader_decision.get("position_size", 10),
            "leverage": trader_decision.get("leverage", 10),
            "stop_loss": risk_result.get("stop_loss"),
            "take_profit": risk_result.get("take_profit"),
            "reason": f"{trader_decision.get('reason', '')} | 风控: {risk_result.get('reason', '')}",
            "tech_report": tech_report[:500],
            "news_report": news_report[:500],
            "bullish_arg": bullish_arg[:300],
            "bearish_arg": bearish_arg[:300],
            "approved": risk_result.get("approved", True)
        }
    
    def _technical_analyst(self, price: float, indicators: Dict) -> str:
        prompt = f"""你是资深技术分析师，分析以下BTC技术指标：

当前价格: ${price:,.2f}

技术指标数据:
- RSI(14): {indicators.get('rsi', 0):.2f}
- MACD: {indicators.get('macd', 0):.2f}
- MACD Signal: {indicators.get('macd_signal', 0):.2f}  
- MACD Hist: {indicators.get('macd_hist', 0):.2f}
- MA5: {indicators.get('ma5', 0):.2f}
- MA10: {indicators.get('ma10', 0):.2f}
- MA20: {indicators.get('ma20', 0):.2f}
- MA60: {indicators.get('ma60', 0):.2f}
- BB Upper: {indicators.get('bb_upper', 0):.2f}
- BB Middle: {indicators.get('bb_middle', 0):.2f}
- BB Lower: {indicators.get('bb_lower', 0):.2f}
- ATR: {indicators.get('atr', 0):.2f}
- ADX: {indicators.get('adx', 0):.2f}

请分析:
1. MACD金叉/死叉状态
2. RSI超买超卖判断
3. 布林带位置
4. 趋势强度(ADX)
5. 短期走势判断

用中文，简洁专业。"""
        
        return self._call_llm("你是资深技术分析师，擅长技术分析。", prompt)
    
    def _news_analyst(self, news: str) -> str:
        if not news:
            news = "近期无重大新闻，市场相对平静"
        
        prompt = f"""你是宏观和加密货币新闻分析师：

新闻内容:
{news}

请分析:
1. 新闻对市场的影响
2. 市场情绪变化
3. 短期走势判断

用中文简洁回答。"""
        
        return self._call_llm("你是新闻分析师，分析市场影响。", prompt)
    
    def _bullish_researcher(self, tech: str, news: str) -> str:
        prompt = f"""你是看多的研究员，根据以下分析提出做多理由：

技术分析:
{tech}

新闻分析:
{news}

请提出做多理由，并质疑做空观点。"""
        
        return self._call_llm("你是看多研究员，提出做多理由。", prompt)
    
    def _bearish_researcher(self, tech: str, news: str) -> str:
        prompt = f"""你是看空的研究员，根据以下分析提出做空理由：

技术分析:
{tech}

新闻分析:
{news}

请提出做空理由，并质疑做多观点。"""
        
        return self._call_llm("你是看空研究员，提出做空理由。", prompt)
    
    def _trader(self, price: float, tech: str, news: str, bull: str, bear: str) -> Dict:
        prompt = f"""你是专业交易员，综合所有分析做出最终决策：

当前价格: ${price:,.2f}

技术分析:
{tech}

新闻分析:
{news}

多头观点:
{bull}

空头观点:
{bear}

请输出JSON格式决策，包括具体的止损和止盈价格:
{{
    "action": "buy/sell/hold",
    "confidence": 0.0-1.0,
    "position_size": 5-20,
    "leverage": 5-20,
    "stop_loss": 止损价格(具体数值),
    "take_profit": 止盈价格(具体数值),
    "reason": "决策理由"
}}

注意：
- stop_loss 和 take_profit 请给出具体的价格数值
- 止损应该在当前价格下方，止盈应该在当前价格上方
- 根据技术分析选择合适的支撑/阻力位设置止损止盈

只输出JSON。"""
        
        result = self._call_llm("你是专业交易员，做出交易决策。", prompt, True)
        decision = self._parse_json(result)
        
        return {
            "action": decision.get("action", "hold"),
            "confidence": decision.get("confidence", 0),
            "position_size": decision.get("position_size", 10),
            "leverage": decision.get("leverage", 10),
            "stop_loss": decision.get("stop_loss"),
            "take_profit": decision.get("take_profit"),
            "reason": decision.get("reason", "")
        }
    
    def _risk_manager(self, decision: Dict, price: float) -> Dict:
        stop_loss = decision.get('stop_loss')
        take_profit = decision.get('take_profit')
        
        # 计算AI给出的止损止盈比例
        if decision.get('action') == 'buy' and stop_loss:
            sl_pct = (price - stop_loss) / price * 100
        elif decision.get('action') == 'sell' and stop_loss:
            sl_pct = (stop_loss - price) / price * 100
        else:
            sl_pct = 0
        
        if decision.get('action') == 'buy' and take_profit:
            tp_pct = (take_profit - price) / price * 100
        elif decision.get('action') == 'sell' and take_profit:
            tp_pct = (price - take_profit) / price * 100
        else:
            tp_pct = 0
        
        # 如果AI没给出止损止盈，使用默认值
        if not stop_loss:
            stop_loss = price * 0.95 if decision.get('action') == 'buy' else price * 1.05
        if not take_profit:
            take_profit = price * 1.10 if decision.get('action') == 'buy' else price * 0.90
        
        prompt = f"""你是风控经理，审核交易提案：

交易决策:
- 操作: {decision.get('action')}
- 置信度: {decision.get('confidence', 0)}
- 仓位: {decision.get('position_size', 10)} USDT
- 杠杆: {decision.get('leverage', 10)}x
- 止损价格: ${stop_loss:.2f} (距当前价 {sl_pct:.1f}%)
- 止盈价格: ${take_profit:.2f} (距当前价 {tp_pct:.1f}%)
- 理由: {decision.get('reason', '')}

当前价格: ${price:,.2f}
初始资金: ${self.config.INITIAL_BALANCE} USDT

风控规则:
- 单笔最大亏损: 15%
- 杠杆限制: 最高20倍
- 最小交易: 5 USDT
- 盈亏比至少 1:1.5

请输出JSON审核结果:
{{
    "approved": true/false,
    "action": "buy/sell/hold/reject",
    "stop_loss": 调整后的止损价格(如有调整),
    "take_profit": 调整后的止盈价格(如有调整),
    "reason": "审核理由"
}}

只输出JSON。"""
        
        result = self._call_llm("你是风控经理，控制风险。", prompt, True)
        risk = self._parse_json(result)
        
        # 如果风控没有调整止损止盈，使用AI给出的值
        adjusted_sl = risk.get("stop_loss") if risk.get("stop_loss") else stop_loss
        adjusted_tp = risk.get("take_profit") if risk.get("take_profit") else take_profit
        
        return {
            "approved": risk.get("approved", True),
            "action": risk.get("action", decision.get("action")),
            "stop_loss": adjusted_sl,
            "take_profit": adjusted_tp,
            "reason": risk.get("reason", "")
        }


def create_btc_agent(config: type = Config) -> BTCRadingAgents:
    """创建BTC TradingAgents实例"""
    return BTCRadingAgents(config)


class TradingAgent:
    """兼容旧接口"""
    def __init__(self, config: type = Config):
        self.config = config
        self.agent = BTCRadingAgents(config)
    
    def analyze(self, ticker: str, date: str, market_data: Dict) -> Dict:
        price = market_data.get("price", 0)
        indicators = market_data.get("indicators", {})
        news = market_data.get("news", "")
        
        return self.agent.run_analysis(price, indicators, news)
