.PHONY: help stats sync-readme-stats dashboard dashboard-mock dashboard-test clean audit-skills install install-dry-run install-force uninstall uninstall-force remove-skills remove-skills-dry-run

DASHBOARD_PORT ?= 8000
MOCK_COUNT ?= 500

help:
	@echo "可用命令："
	@echo "  make install            - 安装 DIY profile 中的技能"
	@echo "  make install-dry-run    - 预览安装动作"
	@echo "  make uninstall          - 卸载技能软链接"
	@echo "  make audit-skills       - 审计技能数量、重名和功能重叠"
	@echo "  make stats              - 查看技能使用统计"
	@echo "  make dashboard          - 启动本地统计看板"
	@echo "  make dashboard-mock     - 用 500 次内存 Mock 数据预览看板"
	@echo "  make dashboard-test     - 运行看板服务测试"
	@echo "  make clean              - 清理缓存文件"

install:
	@bash scripts/install_team_bundle.sh --profile diy

install-dry-run:
	@bash scripts/install_team_bundle.sh --profile diy --dry-run

install-force:
	@bash scripts/install_team_bundle.sh --profile diy --force

uninstall:
	@bash scripts/install_team_bundle.sh --profile diy --uninstall

uninstall-force:
	@bash scripts/install_team_bundle.sh --profile diy --uninstall --force

audit-skills:
	@./scripts/audit-skills

stats:
	@./scripts/skill-stats view

sync-readme-stats:
	@./scripts/skill-stats sync-readme

dashboard:
	@python3 skills/platform/skill-usage-tracker/scripts/dashboard_server.py --port $(DASHBOARD_PORT) --open

dashboard-mock:
	@python3 skills/platform/skill-usage-tracker/scripts/dashboard_server.py --port $(DASHBOARD_PORT) --mock-count $(MOCK_COUNT) --open

dashboard-test:
	@python3 -m unittest discover -s tests -p 'test_dashboard_server.py'

clean:
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

remove-skills:
	@bash scripts/remove_skills.sh

remove-skills-dry-run:
	@bash scripts/remove_skills.sh --dry-run
