import inspect 
from ast import *
from typing import Dict                                    
from typing import Tuple                                   
from typing import List as TList                                 
from sys import maxsize                                                                                                
from random import randint                                 
                                                                         
                                                       
class DuplicateCallFinder(NodeVisitor):                                     
    """ A NodeVisitor that walks the nodes of a Python AST and finds any
    duplicate function calls.                                                                                          
    """                                                                                                                
    def __init__(self):                                    
        self.calls: Dict[str, Tuple[Call, int]] = {}       
                                                                 
    def visit_Call(self, call: Call) -> None:                                                                          
        call_hash = dump(call)                             
        _, current_count = self.calls.get(call_hash, (call, 0))
        self.calls[call_hash] = (call, current_count + 1)  
                                                                           
    @property                                                             
    def duplicate_calls(self) -> TList[Call]:              
        return [                                           
            call                                           
            for _, (call, call_count) in self.calls.items()
            if call_count > 1                                                                                          
        ]                                                  
                                                           

class RenameTargetVariableNames(NodeTransformer):          
    """ A NodeTransformer that walks the nodes of a Python function AST and                                            
    renames variable names to prevent duplicates.                                                                      
    """                                                    
    def __init__(self):                                    
        self.variables_to_replace_stack = []
        self.assign_mode = False                           
                                                        
    def visit_comp(self, node):
        # Visit all of the comprehensions in the node and make sure to add
        # the target variable names to the stack of variable names to
        # replace.             
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
                                                                                                                       
        # Make sure we pop the variables off the stack of variable names
        # to replace so we don't continue to replace variable names
        # outside of the scope of the current comprehension
        self.variables_to_replace_stack[:-len(node.generators)]
        return node                                        

                                                                                                                       
    # Optimize list, set and dict comps, and generators the same way
    visit_ListComp     = visit_comp                        
    visit_SetComp      = visit_comp                        
    visit_DictComp     = visit_comp                                                                                    
    visit_GeneratorExp = visit_comp                        
                                                           
    def visit_Name(self, node):                            
        # Assignments to target varibles in a comprehension (if the stack
        # is empty, we're not in a comprehension)          
        if isinstance(node.ctx, Store) and self.variables_to_replace_stack:
            random_int = randint(0, maxsize)               
            new_id = f'{node.id}__{random_int}'            
            self.variables_to_replace_stack[-1][node.id] = new_id
            node.id = new_id                                                                                           
                                                           
        # Loading the value of target varibles in a comprehension (if the
        # stack is empty, we're not in a comprehension)
        elif isinstance(node.ctx, Load) and self.variables_to_replace_stack:
            flattened_variables_to_replace = {}
            for variables_to_replace in self.variables_to_replace_stack:                                               
                flattened_variables_to_replace.update(variables_to_replace)                                            
                                                           
            if node.id in flattened_variables_to_replace:  
                node.id = flattened_variables_to_replace[node.id]
        return node                                                                                                    
                                                           
                                                           
class OptimizeComprehensions(NodeTransformer):             
    """ A NodeTransformer that walks the nodes of a Python function AST and
    optimizes list comprehensions by eliminating duplicate function calls.
    """                                                    
                                                           
    def __init__(self):                                    
        self.calls_to_replace_stack = []                   
                                                                                                                       
    def visit_FunctionDef(self, node):                     
        RenameTargetVariableNames().visit(node)            

        self.generic_visit(node)                           
        # Remove the fast_comprehensions decorator from the method so we don't                                         
        # infinitely recurse                                                                                           
        decorators = node.decorator_list                   
        node.decorator_list = [                            
            decorator
            for decorator in node.decorator_list           
            if decorator.id != 'optimize_comprehensions'
        ]
        return node                                        
                                                           
    def visit_comp(self, node):
        # Find all functions that are called multiple times with the same
        # arguments as we will replace them with one variable
        call_visitor = DuplicateCallFinder()               
        call_visitor.visit(node)                           
                                                           
        # Keep track of what calls we need to replace using a stack so we
        # support nested comprehensions                    
        self.calls_to_replace_stack.append(call_visitor.duplicate_calls)
                                      
        # Visit children of this list comprehension and replace calls
        self.generic_visit(node)

        # Gather the existing if statements as we need to move them to the
        # last comprehension generator (or there will be issues looking up
        # identifiers)
        existing_ifs = []
        for generator in node.generators:
            existing_ifs += generator.ifs
            generator.ifs = []

        # Create a new for loop for each function call result that we want
        # to alias and add it to the list comprehension
        for call in call_visitor.duplicate_calls:
            new_comprehension = comprehension(
                # Notice that we're storing (Store) the result of the call
                # instead of loading it (Load)
                target=Name(
                    id=self._identifier_from_Call(call),
                    ctx=Store()
                ),
                iter=List(elts=[call], ctx=Load()),
                ifs=[],
                is_async=0,
            )
            # Add linenos and other things the compile needs to node
            fix_missing_locations(new_comprehension)
            node.generators.append(new_comprehension)

        node.generators[-1].ifs = existing_ifs

        # Make sure we clear the calls to replace so we don't replace other
        # calls outside of the scope of this current list comprehension
        self.calls_to_replace_stack.pop()
        return node

    # Optimize list, set and dict comps, and generators the same way
    visit_ListComp     = visit_comp
    visit_SetComp      = visit_comp
    visit_DictComp     = visit_comp
    visit_GeneratorExp = visit_comp

    def visit_Call(self, node):
        # Flatten the stack of calls to replace
        call_hashes = [
            dump(call)
            for calls_to_replace in self.calls_to_replace_stack
            for call in calls_to_replace
        ]

        if dump(node) in call_hashes:
            name_node = Name(id=self._identifier_from_Call(node), ctx=Load())
            # Add linenos and other things the compile needs to the new node
            fix_missing_locations(name_node)
            return name_node

        return node


    def _identifier_from_Call(self, node):
        return '__{}'.format(abs(hash(dump(node))))


def optimize_comprehensions(func):
    source = inspect.getsource(func)
    in_node = parse(source)
    out_node = OptimizeComprehensions().visit(in_node)
    new_func_name = out_node.body[0].name
    func_scope = func.__globals__
    # Compile the new method in the old methods scope
    exec(compile(out_node, '<string>', 'exec'), func_scope)
    return func_scope[new_func_name]
