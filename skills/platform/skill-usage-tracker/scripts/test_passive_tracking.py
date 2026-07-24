#!/usr/bin/env python3
"""
技能统计测试脚本

用于本地演示统计文件写入，不参与仓库正式“显式 record 优先”流程。
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# 数据文件路径：与当前主实现保持一致，默认写用户根目录主文件
DATA_FILE = Path.home() / "usage_stats.json"

def load_stats():
    """加载统计数据"""
    if not DATA_FILE.exists():
        return {"skills": {}, "total_usage": 0}
    
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"skills": {}, "total_usage": 0}

def save_stats(stats):
    """保存统计数据"""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def simulate_conversation():
    """模拟一轮本地测试写入"""
    
    # 模拟一轮对话里收集到的技能记录（测试脚本本地拼装）
    conversation_skills = []
    
    print("🤖 AI：开始本地统计写入演示")
    print("=" * 60)
    
    # 模拟用户使用了几个技能
    skills_used = [
        ("brainstorming", "优化 skill-usage-tracker"),
        ("ai-pair-programmer", "添加使用记录到技能"),
        ("skill-usage-tracker", "查看技能统计"),
    ]
    
    for skill_name, context in skills_used:
        print(f"👤 用户：使用 {skill_name} - {context}")
        print(f"🤖 AI：[记录到内存] {skill_name}: {context}")
        conversation_skills.append((skill_name, context))
        print()
    
    # 测试脚本结束后统一写入
    print("=" * 60)
    print("🤖 AI：测试结束，统一写入记录...")
    print()
    
    stats = load_stats()
    
    for skill_name, context in conversation_skills:
        # 初始化技能数据
        if skill_name not in stats["skills"]:
            stats["skills"][skill_name] = {
                "count": 0,
                "last_used": None,
                "history": []
            }
        
        # 更新技能数据
        skill_data = stats["skills"][skill_name]
        skill_data["count"] += 1
        skill_data["last_used"] = datetime.now().isoformat()
        
        # 添加历史记录
        timestamp = datetime.now().isoformat()
        skill_data["history"].insert(0, {
            "timestamp": timestamp,
            "context": context
        })
        
        # 保留最近50条
        if len(skill_data["history"]) > 50:
            skill_data["history"] = skill_data["history"][:50]
        
        print(f"✅ 已记录：{skill_name} (第 {skill_data['count']} 次使用)")
    
    # 更新总使用次数
    stats["total_usage"] = sum(s["count"] for s in stats["skills"].values())
    
    # 保存数据
    save_stats(stats)
    
    print()
    print("=" * 60)
    print("✨ 写入完成！")
    print()
    
    # 显示统计
    print("📊 当前技能使用排行：")
    print("-" * 60)
    
    sorted_skills = sorted(
        stats["skills"].items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )
    
    for skill, data in sorted_skills[:10]:
        print(f"{skill:30} | {data['count']:5} 次 | 最后使用: {data['last_used'][:10] if data['last_used'] else 'N/A'}")
    
    print(f"\n总计使用次数：{stats['total_usage']}")

def main():
    """主函数"""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║        被动记录机制测试                                    ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    
    simulate_conversation()
    
    print()
    print("💡 说明：")
    print("  - 这是一个本地测试/演示脚本，不代表仓库正式调用约束")
    print("  - 正式流程仍应优先使用 scripts/skill-stats record 显式记录")
    print("  - 默认统计文件为 ~/usage_stats.json")
    print()
    print("📝 查看完整统计：")
    print("  scripts/skill-stats view")

if __name__ == "__main__":
    main()
