# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

OP_PRECEDENCE = {
    op: precedence
    for precedence, ops in enumerate(
        [
            ["Lambda"],  # lambda x: x + 1
            ["IfExp"],  # 1 if True else 2
            ["or"],
            ["and"],
            ["not"],
            ["Compare"],  # in, not in, is, is not, <, <=, >, >=, !=, ==
            ["|"],
            ["^"],
            ["&"],
            ["<<", ">>"],
            ["+", "-"],
            ["*", "@", "/", "//", "%"],
            ["UnaryOp"],  # +, -, ~
            ["**"],
            ["Await"],
        ]
    )
    for op in ops
}
