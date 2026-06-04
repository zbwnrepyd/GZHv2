import json
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))


def run_text_finalize_script(script_body: str):
    panel_path = os.path.join(ROOT, "webapp", "static", "js", "editor", "text-finalize-panel.js")
    script = f"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync({json.dumps(panel_path)}, 'utf8');
const context = {{
  document: {{ addEventListener: () => {{}} }},
  console,
}};
vm.createContext(context);
vm.runInContext(code + "\\n" + {json.dumps(script_body)}, context);
"""
    output = subprocess.check_output(["node", "-e", script], text=True)
    return json.loads(output)


class EditorLineChoiceTests(unittest.TestCase):
    def test_text_finalize_panel_renders_field_version_choices(self):
        html = run_text_finalize_script(
            """
TextFinalizePanel._cards = [{
  card_id: 'card_01',
  card_title: '首页',
  items: [
    { item_type: 'field', item_key: 'company_type', display_role: 'subtitle' },
    { item_type: 'field', item_key: 'missing_field', display_role: 'body' },
  ],
}];
TextFinalizePanel._fieldsByKey = {
  company_type: {
    label: '公司类型',
    versions: {
      standard: '标准版',
      business: '商业版',
      spread: '传播版',
    },
    final_value: '已定稿',
    status: 'confirmed',
  },
};
console.log(JSON.stringify(TextFinalizePanel._cardContent('card_01')));
"""
        )

        self.assertIn('公司类型', html)
        self.assertIn('标准版', html)
        self.assertIn('商业版', html)
        self.assertIn('传播版', html)
        self.assertIn('已定稿', html)
        self.assertNotIn('missing_field', html)


if __name__ == "__main__":
    unittest.main()
