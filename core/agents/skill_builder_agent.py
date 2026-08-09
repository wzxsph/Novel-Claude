import json
import os
import re
import shutil
from pathlib import Path

from utils import config
from utils.llm_client import get_client
from core.novel_context import NovelContext
from core.plugin_manager import PluginManager

class SkillBuilderAgent:
    """
    负责 “从0到1” 动态编写并加载 V3 插件体系（Meta-Generation）的智能体。
    """
    def __init__(self, context: NovelContext, plugin_mgr: PluginManager):
        self.name = "SkillBuilderAgent"
        self.context = context
        self.plugin_mgr = plugin_mgr
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self):
        # 读取规范文档作为核心知识
        prompt = "你是 Novel-Claude V3 系统的核心插件架构师。你的任务是根据用户的需求，编写合规的 Python 插件代码（BaseSkill 的子类）。\n\n"
        try:
            template_path = config.PROJECT_ROOT / "reference" / "Skill与Agent开发模板规范.md"
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    prompt += "【开发规范与模板如下】：\n" + f.read() + "\n\n"
        except Exception:
            pass
            
        prompt += """
必须严格遵循 BaseSkill 规范。并且你的输出最终通过 save_skill_code 工具落盘生效。
绝不要在生成代码时省略任何逻辑！
"""
        return prompt

    def get_tools(self):
        return [{
            "type": "function",
            "function": {
                "name": "save_skill_code",
                "description": "当你编写好插件完整的 Python 代码后，调用此工具将代码落盘到 skills 目录下，并进行热更新加载生效。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_folder_name": {"type": "string", "description": "插件的文件夹英文名，如 'ext_sanity_system'"},
                        "python_code": {"type": "string", "description": "完整的、可直接运行的 python 源码文件内容。"},
                        "readme_content": {"type": "string", "description": "Markdown 格式的插件说明文档，详细介绍插件的作用、用法以及内部机制。"}
                    },
                    "required": ["skill_folder_name", "python_code", "readme_content"]
                }
            }
        }]

    @staticmethod
    def _resolve_skill_dir(folder_name: str) -> Path:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", folder_name or ""):
            raise ValueError(
                "skill_folder_name 只能使用小写字母、数字和下划线，且必须以字母开头"
            )
        skills_root = (config.PROJECT_ROOT / "skills").resolve()
        candidate = (skills_root / folder_name).resolve()
        candidate.relative_to(skills_root)
        return candidate

    def build_skill(self, user_request: str) -> bool:
        print(f"\\n[🤖 {self.name}] 正在分析您的需求，构思插件逻辑...")
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"请为我开发一个外挂插件。需求:\n{user_request}\n\n完成后请调用 save_skill_code 工具写入系统。"}
        ]
        
        response = get_client().chat.completions.create(
            model=config.MODEL_ID,
            messages=messages,
            tools=self.get_tools(),
            temperature=0.2
        )
        
        msg = response.choices[0].message
        
        if getattr(msg, 'tool_calls', None):
            tool_call = msg.tool_calls[0]
            if tool_call.function.name == "save_skill_code":
                args = json.loads(tool_call.function.arguments)
                folder_name = args['skill_folder_name']
                code = args['python_code']
                readme = args.get('readme_content', f"# {folder_name}\\n\\n自动生成的插件说明。")

                try:
                    compile(code, f"<generated-skill:{folder_name}>", "exec")
                except (SyntaxError, ValueError) as exc:
                    print(f"[ERROR] 生成的插件代码无法编译，未写入磁盘: {exc}")
                    return False
                
                # 写入代码
                try:
                    skill_dir = self._resolve_skill_dir(folder_name)
                except ValueError as exc:
                    print(f"[ERROR] 拒绝不安全的插件目录名: {exc}")
                    return False
                directory_existed = skill_dir.exists()
                tracked_files = [
                    skill_dir / "README.md",
                    skill_dir / "__init__.py",
                    skill_dir / "skill.py",
                ]
                previous = {
                    path: path.read_bytes() if path.is_file() else None
                    for path in tracked_files
                }
                skill_dir.mkdir(parents=True, exist_ok=True)
                
                # 创建 README.md
                with (skill_dir / "README.md").open("w", encoding="utf-8") as f:
                    f.write(readme)
                
                # 创建 __init__.py
                with (skill_dir / "__init__.py").open("w", encoding="utf-8") as f:
                    f.write("# Auto-generated skill package\n")
                    
                # 创建 skill.py
                skill_file = skill_dir / "skill.py"
                with skill_file.open("w", encoding="utf-8") as f:
                    f.write(code)
                    
                print(f"[✓] 插件代码已生成并写入: {skill_file}")
                
                # 热更新加载
                if self.plugin_mgr.hot_reload(folder_name):
                    return True

                # Hot reload is transactional in PluginManager. Restore the
                # source files as well so the next process start still sees the
                # last working version.
                if directory_existed:
                    for path, old_content in previous.items():
                        if old_content is None:
                            path.unlink(missing_ok=True)
                        else:
                            path.write_bytes(old_content)
                else:
                    shutil.rmtree(skill_dir)
                print("[ERROR] 插件加载失败，已恢复写入前的文件。")
                return False
                
        print(f"[❌] 开发失败，大模型未能调用正确的代码保存工具。模型输出:\n{msg.content}")
        return False
