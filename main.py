def tokenize(expression):
    tokens = expression.split()
    return tokens

class Node:
    pass

class Number(Node):
    def __init__(self, value):
        self.value = value

class BinOp(Node):
    def __init__(self, left, right, op):
        self.left = left
        self.right = right
        self.op = op

def parse(tokens):
    stack = []
    for token in tokens:
        if token.isdigit():
            stack.append(Number(int(token)))
        else:
            right = stack.pop()
            left = stack.pop()
            stack.append(BinOp(left, right, token))
    return stack[0]

from llvmlite import ir, binding

binding.initialize()
binding.initialize_native_target()
binding.initialize_native_asmprinter()

class LLVMCodeGen:
    def __init__(self):
        self.module = ir.Module(name=__file__)
        self.builder = None
        self.func = None
        self.block = None

    def generate_code(self, node):
        self.func = ir.Function(self.module, ir.FunctionType(ir.IntType(32), ()), name="main")
        self.block = self.func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(self.block)
        result = self.codegen(node)
        self.builder.ret(result)
        return str(self.module)

    def codegen(self, node):
        if isinstance(node, Number):
            return ir.Constant(ir.IntType(32), node.value)
        elif isinstance(node, BinOp):
            left = self.codegen(node.left)
            right = self.codegen(node.right)
            if node.op == 'add':
                return self.builder.add(left, right)
            elif node.op == 'sub':
                return self.builder.sub(left, right)
            elif node.op == 'mul':
                return self.builder.mul(left, right)
            elif node.op == 'div':
                return self.builder.sdiv(left, right)
            else:
                raise ValueError("Unsupported operation")

print("Stack Compiler")
codegen = LLVMCodeGen()
expression = input("> ")
tokens = tokenize(expression)
ast = parse(tokens)
llvm_ir = codegen.generate_code(ast)
print(llvm_ir)

from llvmlite import binding as llvm

llvm.initialize()
llvm.initialize_native_target()
llvm.initialize_native_asmprinter()

def compile_ir(ir_code):
    target = llvm.Target.from_default_triple()
    target_machine = target.create_target_machine()
    backing_mod = llvm.parse_assembly(ir_code)
    engine = llvm.create_mcjit_compiler(backing_mod, target_machine)

    engine.finalize_object()
    engine.run_static_constructors()
    return engine

engine = compile_ir(llvm_ir)
main_ptr = engine.get_function_address("main")

import ctypes
main_func = ctypes.CFUNCTYPE(ctypes.c_int32)(main_ptr)
result = main_func()
print("Result:", result)
