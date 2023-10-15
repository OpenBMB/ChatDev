# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""_filter_stmts and helper functions.

This method gets used in LocalsDictnodes.NodeNG._scope_lookup.
It is not considered public.
"""

from __future__ import annotations

from astroid import nodes


def _get_filtered_node_statements(
    base_node: nodes.NodeNG, stmt_nodes: list[nodes.NodeNG]
) -> list[tuple[nodes.NodeNG, nodes.Statement]]:
    statements = [(node, node.statement(future=True)) for node in stmt_nodes]
    # Next we check if we have ExceptHandlers that are parent
    # of the underlying variable, in which case the last one survives
    if len(statements) > 1 and all(
        isinstance(stmt, nodes.ExceptHandler) for _, stmt in statements
    ):
        statements = [
            (node, stmt) for node, stmt in statements if stmt.parent_of(base_node)
        ]
    return statements


def _is_from_decorator(node) -> bool:
    """Return whether the given node is the child of a decorator."""
    return any(isinstance(parent, nodes.Decorators) for parent in node.node_ancestors())


def _get_if_statement_ancestor(node: nodes.NodeNG) -> nodes.If | None:
    """Return the first parent node that is an If node (or None)."""
    for parent in node.node_ancestors():
        if isinstance(parent, nodes.If):
            return parent
    return None


def _filter_stmts(base_node: nodes.NodeNG, stmts, frame, offset):
    """Filter the given list of statements to remove ignorable statements.

    If base_node is not a frame itself and the name is found in the inner
    frame locals, statements will be filtered to remove ignorable
    statements according to base_node's location.

    :param stmts: The statements to filter.
    :type stmts: list(nodes.NodeNG)

    :param frame: The frame that all of the given statements belong to.
    :type frame: nodes.NodeNG

    :param offset: The line offset to filter statements up to.
    :type offset: int

    :returns: The filtered statements.
    :rtype: list(nodes.NodeNG)
    """
    # if offset == -1, my actual frame is not the inner frame but its parent
    #
    # class A(B): pass
    #
    # we need this to resolve B correctly
    if offset == -1:
        myframe = base_node.frame().parent.frame()
    else:
        myframe = base_node.frame()
        # If the frame of this node is the same as the statement
        # of this node, then the node is part of a class or
        # a function definition and the frame of this node should be the
        # the upper frame, not the frame of the definition.
        # For more information why this is important,
        # see Pylint issue #295.
        # For example, for 'b', the statement is the same
        # as the frame / scope:
        #
        # def test(b=1):
        #     ...
        if (
            base_node.parent
            and base_node.statement(future=True) is myframe
            and myframe.parent
        ):
            myframe = myframe.parent.frame()

    mystmt: nodes.Statement | None = None
    if base_node.parent:
        mystmt = base_node.statement(future=True)

    # line filtering if we are in the same frame
    #
    # take care node may be missing lineno information (this is the case for
    # nodes inserted for living objects)
    if myframe is frame and mystmt and mystmt.fromlineno is not None:
        assert mystmt.fromlineno is not None, mystmt
        mylineno = mystmt.fromlineno + offset
    else:
        # disabling lineno filtering
        mylineno = 0

    _stmts = []
    _stmt_parents = []
    statements = _get_filtered_node_statements(base_node, stmts)
    for node, stmt in statements:
        # line filtering is on and we have reached our location, break
        if stmt.fromlineno and stmt.fromlineno > mylineno > 0:
            break
        # Ignore decorators with the same name as the
        # decorated function
        # Fixes issue #375
        if mystmt is stmt and _is_from_decorator(base_node):
            continue
        if node.has_base(base_node):
            break

        if isinstance(node, nodes.EmptyNode):
            # EmptyNode does not have assign_type(), so just add it and move on
            _stmts.append(node)
            continue

        assign_type = node.assign_type()
        _stmts, done = assign_type._get_filtered_stmts(base_node, node, _stmts, mystmt)
        if done:
            break

        optional_assign = assign_type.optional_assign
        if optional_assign and assign_type.parent_of(base_node):
            # we are inside a loop, loop var assignment is hiding previous
            # assignment
            _stmts = [node]
            _stmt_parents = [stmt.parent]
            continue

        if isinstance(assign_type, nodes.NamedExpr):
            # If the NamedExpr is in an if statement we do some basic control flow inference
            if_parent = _get_if_statement_ancestor(assign_type)
            if if_parent:
                # If the if statement is within another if statement we append the node
                # to possible statements
                if _get_if_statement_ancestor(if_parent):
                    optional_assign = False
                    _stmts.append(node)
                    _stmt_parents.append(stmt.parent)
                # If the if statement is first-level and not within an orelse block
                # we know that it will be evaluated
                elif not if_parent.is_orelse:
                    _stmts = [node]
                    _stmt_parents = [stmt.parent]
                # Else we do not known enough about the control flow to be 100% certain
                # and we append to possible statements
                else:
                    _stmts.append(node)
                    _stmt_parents.append(stmt.parent)
            else:
                _stmts = [node]
                _stmt_parents = [stmt.parent]

        # XXX comment various branches below!!!
        try:
            pindex = _stmt_parents.index(stmt.parent)
        except ValueError:
            pass
        else:
            # we got a parent index, this means the currently visited node
            # is at the same block level as a previously visited node
            if _stmts[pindex].assign_type().parent_of(assign_type):
                # both statements are not at the same block level
                continue
            # if currently visited node is following previously considered
            # assignment and both are not exclusive, we can drop the
            # previous one. For instance in the following code ::
            #
            #   if a:
            #     x = 1
            #   else:
            #     x = 2
            #   print x
            #
            # we can't remove neither x = 1 nor x = 2 when looking for 'x'
            # of 'print x'; while in the following ::
            #
            #   x = 1
            #   x = 2
            #   print x
            #
            # we can remove x = 1 when we see x = 2
            #
            # moreover, on loop assignment types, assignment won't
            # necessarily be done if the loop has no iteration, so we don't
            # want to clear previous assignments if any (hence the test on
            # optional_assign)
            if not (optional_assign or nodes.are_exclusive(_stmts[pindex], node)):
                del _stmt_parents[pindex]
                del _stmts[pindex]

        # If base_node and node are exclusive, then we can ignore node
        if nodes.are_exclusive(base_node, node):
            continue

        # An AssignName node overrides previous assignments if:
        #   1. node's statement always assigns
        #   2. node and base_node are in the same block (i.e., has the same parent as base_node)
        if isinstance(node, (nodes.NamedExpr, nodes.AssignName)):
            if isinstance(stmt, nodes.ExceptHandler):
                # If node's statement is an ExceptHandler, then it is the variable
                # bound to the caught exception. If base_node is not contained within
                # the exception handler block, node should override previous assignments;
                # otherwise, node should be ignored, as an exception variable
                # is local to the handler block.
                if stmt.parent_of(base_node):
                    _stmts = []
                    _stmt_parents = []
                else:
                    continue
            elif not optional_assign and mystmt and stmt.parent is mystmt.parent:
                _stmts = []
                _stmt_parents = []
        elif isinstance(node, nodes.DelName):
            # Remove all previously stored assignments
            _stmts = []
            _stmt_parents = []
            continue
        # Add the new assignment
        _stmts.append(node)
        if isinstance(node, nodes.Arguments) or isinstance(
            node.parent, nodes.Arguments
        ):
            # Special case for _stmt_parents when node is a function parameter;
            # in this case, stmt is the enclosing FunctionDef, which is what we
            # want to add to _stmt_parents, not stmt.parent. This case occurs when
            # node is an Arguments node (representing varargs or kwargs parameter),
            # and when node.parent is an Arguments node (other parameters).
            # See issue #180.
            _stmt_parents.append(stmt)
        else:
            _stmt_parents.append(stmt.parent)
    return _stmts
