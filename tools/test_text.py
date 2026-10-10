# -*- coding: utf-8 -*-
"""文本处理的单元测试（只用标准库）：  python -m unittest discover -s tools -p "test_*.py" -v

这些函数改的是全站每一页的文字，出错不会报警、只会悄悄把内容改坏，所以把边界情况钉死在这里。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402

L, R = "\u201c", "\u201d"      # “ ”


class CurlyHtml(unittest.TestCase):
    def check(self, src, expected):
        got = build.curly_html(src)
        self.assertEqual(got, expected)
        self.assertEqual(build.curly_html(got), got, "应当幂等（再处理一遍不变）")

    def test_plain_text(self):
        self.check('<p class="a">他说"积木"很好</p>', '<p class="a">他说%s积木%s很好</p>' % (L, R))

    def test_attributes_untouched_even_with_gt(self):
        self.check('<a href="x" title="a>b">点"贪心"</a>', '<a href="x" title="a>b">点%s贪心%s</a>' % (L, R))

    def test_single_quoted_attribute_containing_double_quotes(self):
        self.check("<a title='say \"你好\"'>x</a>", "<a title='say \"你好\"'>x</a>")

    def test_pairs_across_inline_tags(self):
        self.check('<p>点"<b>贪心</b>"：</p>', '<p>点%s<b>贪心</b>%s：</p>' % (L, R))

    def test_math_untouched(self):
        self.check('<p>$a<b$ 和 "中文" 以及 $"x"$</p>', '<p>$a<b$ 和 %s中文%s 以及 $"x"$</p>' % (L, R))
        self.check('<p>$$a<b$$ "中文"</p>', '<p>$$a<b$$ %s中文%s</p>' % (L, R))
        self.check('<p>$x<y$ <b>"粗体"</b></p>', '<p>$x<y$ <b>%s粗体%s</b></p>' % (L, R))

    def test_script_style_code_pre_textarea_comment_untouched(self):
        self.check('<script>var s = "中文";</script><p>"中文"</p>', '<script>var s = "中文";</script><p>%s中文%s</p>' % (L, R))
        self.check('<p><code>"中文"</code> 与 "中文"</p>', '<p><code>"中文"</code> 与 %s中文%s</p>' % (L, R))
        self.check('<textarea>"中文"</textarea>', '<textarea>"中文"</textarea>')
        self.check('<!-- "中文" --><p>ok</p>', '<!-- "中文" --><p>ok</p>')

    def test_odd_number_of_quotes_left_alone(self):
        self.check('<p>5" 的"中文"</p>', '<p>5" 的"中文"</p>')

    def test_pairs_never_cross_block_tags(self):
        self.check('<p>"中文</p><p>文"</p>', '<p>"中文</p><p>文"</p>')

    def test_english_sentences_untouched(self):
        self.check('<p>"hello" 你好</p>', '<p>"hello" 你好</p>')
        self.check('<p>He said "hi" today</p>', '<p>He said "hi" today</p>')
        self.check('<p>输入 "kitten" 和 "sitting" 吧</p>', '<p>输入 "kitten" 和 "sitting" 吧</p>')

    def test_latin_or_math_quoted_inside_a_chinese_sentence(self):
        self.check('<p>点"Q ← P+Q"可以接着往下加</p>', '<p>点%sQ ← P+Q%s可以接着往下加</p>' % (L, R))
        self.check('<p>霍尔电导出现"$1/3$"的平台</p>', '<p>霍尔电导出现%s$1/3$%s的平台</p>' % (L, R))
        self.check('<p>称为"wired"，两种</p>', '<p>称为%swired%s，两种</p>' % (L, R))

    def test_mixed_english_and_chinese_pairs(self):
        self.check('<p>"a" 中文 "b" 和 "中文"</p>', '<p>"a" 中文 "b" 和 %s中文%s</p>' % (L, R))

    def test_no_quotes_is_a_noop(self):
        self.check("<p>你好</p>", "<p>你好</p>")


class CurlyField(unittest.TestCase):
    def test_math_with_lt_is_protected(self):
        self.assertEqual(build.curly_quotes('素数大致"每 $\\ln x$ 个数里出现一个"，但 $\\sigma<1$'),
                         '素数大致%s每 $\\ln x$ 个数里出现一个%s，但 $\\sigma<1$' % (L, R))

    def test_odd_quotes_untouched(self):
        self.assertEqual(build.curly_quotes('尺寸 5" 和 "中文"'), '尺寸 5" 和 "中文"')

    def test_bare_lt_means_html_so_untouched(self):
        self.assertEqual(build.curly_quotes('a < b 的 "中文"'), 'a < b 的 "中文"')


if __name__ == "__main__":
    unittest.main()
