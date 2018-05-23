import inspect
from ast import *
from typing import Dict
from typing import Tuple
from typing import List as TList
from sys import maxsize
from random import randint
import astpretty


class DuplicateCallFinder(NodeVisitor):

    def __init__(self):
        self.calls = {}

    # traverse nodes and look for function calls, count no of times they are called
    def visit_Call(self, call):
        call_hash = dump(call)
        func_call, current_count = self.calls.get(call_hash, (call, 0))
        self.calls[call_hash] = (call, current_count + 1)

    @property
    def duplicate_calls(self):
        return [call for _, (call, call_count) in self.calls.items() if call_count > 1]


class RenameTargetVariableNames(NodeTransformer):

    def __init__(self):
        self.variables_to_replace_stack = []
        self.assign_mode = False

    def visit_comp(self, node):
        # Visit all of the comprehensions in the node and make sure to add the target variable names to the stack of variable names to replace.
        for generator in node.generators:
            self.visit(generator.iter)
            self.variables_to_replace_stack.append(dict())
            self.visit(generator.target)
            for _if in generator.ifs:
                self.visit(_if)

        # Visit the output expression in the comprehension
        if isinstance(node, DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)

        # Pop variables from the stack from the current context
        self.variables_to_replace_stack[:-len(node.generators)]
        return node

    visit_ListComp = visit_comp
    visit_SetComp = visit_comp
    visit_DictComp = visit_comp
    visit_GeneratorExp = visit_comp

    def visit_Name(self, node):
        # Store to target varibles in a comprehension 
        if isinstance(node.ctx, Store) and self.variables_to_replace_stack:
            random_int = randint(0, maxsize)
            new_id = f'{node.id}__{random_int}'
            self.variables_to_replace_stack[-1][node.id] = new_id
            node.id = new_id

        # Loading the value of target varibles in a comprehension 
        elif isinstance(node.ctx, Load) and self.variables_to_replace_stack:
            flattened_variables_to_replace = {}
            for variables_to_replace in self.variables_to_replace_stack:
                flattened_variables_to_replace.update(variables_to_replace)

            if node.id in flattened_variables_to_replace:
                node.id = flattened_variables_to_replace[node.id]
        return node


class OptimizeComprehensions(NodeTransformer):

    def __init__(self):
        self.calls_to_replace_stack = []

    def visit_FunctionDef(self, node):
        RenameTargetVariableNames().visit(node)

        self.generic_visit(node)
        # remove the  decorator from the method so we don't go into an infinite loop
        decorators = node.decorator_list
        node.decorator_list = [ decorator for decorator in node.decorator_list if decorator.id != 'optimize_comprehensions' ]
        return node

    def visit_comp(self, node):
        # Find all functions that are called multiple times with the same arguments as we will replace them with one variable
        call_visitor = DuplicateCallFinder()
        call_visitor.visit(node)

        # Keep track of what calls we need to replace using a stack so we support nested comprehensions
        self.calls_to_replace_stack.append(call_visitor.duplicate_calls)

        self.generic_visit(node)

        # Gather the existing if statements as we need to move them to the
        # last comprehension generator (or there will be issues looking up identifiers)
        existing_ifs = []
        for generator in node.generators:
            existing_ifs += generator.ifs
            generator.ifs = []

        # Create a new for loop for each function call result that we want to alias and add it to the list comprehension
        for call in call_visitor.duplicate_calls:
            new_comprehension = comprehension(
                # storing the result of the call
                target=Name(
                    id=self._identifier_from_Call(call),
                    ctx=Store()
                ),
                iter=List(elts=[call], ctx=Load()),
                ifs=[],
                is_async=0,
            )
            fix_missing_locations(new_comprehension)
            node.generators.append(new_comprehension)

        node.generators[-1].ifs = existing_ifs
        
        self.calls_to_replace_stack.pop()
        return node

    visit_ListComp = visit_comp
    visit_SetComp = visit_comp
    visit_DictComp = visit_comp
    visit_GeneratorExp = visit_comp

    def visit_Call(self, node):
        call_hashes = [ dump(call) for calls_to_replace in self.calls_to_replace_stack for call in calls_to_replace ]

        if dump(node) in call_hashes:
            name_node = Name(id=self._identifier_from_Call(node), ctx=Load())
            fix_missing_locations(name_node)
            return name_node

        return node

    def _identifier_from_Call(self, node):
        return '__{}'.format(abs(hash(dump(node))))


def optimize_comprehensions(func):
    source = inspect.getsource(func)
    in_node = parse(source)
    astpretty.pprint(in_node)

    out_node = OptimizeComprehensions().visit(in_node)

    print("Modified AST")
    astpretty.pprint(out_node)
    new_func_name = out_node.body[0].name
    func_scope = func.__globals__

    # Compile the new method in the old methods scope
    exec(compile(out_node, '<string>', 'exec'), func_scope)
    return func_scope[new_func_name]
