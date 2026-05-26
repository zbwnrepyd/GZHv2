import json
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))


def run_editor_script(script_body: str):
    editor_path = os.path.join(ROOT, "webapp", "static", "js", "editor.js")
    script = f"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync({json.dumps(editor_path)}, 'utf8');
const context = {{
  document: {{ addEventListener: () => {{}} }},
  URLSearchParams,
  console,
}};
vm.createContext(context);
vm.runInContext(code + "\\n" + {json.dumps(script_body)}, context);
"""
    output = subprocess.check_output(["node", "-e", script], text=True)
    return json.loads(output)


class EditorLineChoiceTests(unittest.TestCase):
    def test_renderable_rows_skip_all_empty_version_and_final_lines(self):
        rows = run_editor_script(
            """
EditorApp.currentCard = 1;
EditorApp.versionChoices = {
  1: {
    standard: '标题\\n\\n标准正文',
    business: '标题\\n\\n商业正文',
    spread: '标题\\n\\n传播正文',
  }
};
EditorApp.finalLinesByCard = { 1: ['标题', '', '标准正文'] };
console.log(JSON.stringify(EditorApp.getRenderableRows()));
"""
        )

        self.assertEqual(rows, [0, 2])


if __name__ == "__main__":
    unittest.main()
