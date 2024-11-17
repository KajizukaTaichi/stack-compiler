from llvmlite import ir, binding
from llvmlite import binding as llvm
import ctypes

def tokenize(expression):
    tokens = []
    current = ""
    is_quote = False
    for i in expression:
        if i == '"':
            is_quote = not is_quote
            current += i
        elif i == ' ' and not is_quote:
            if current:
                tokens.append(current)
                current = ""
        else:
            current += i
    tokens.append(current)
    print(tokens)
    return tokens


class Node:
    pass

class Number(Node):
    def __init__(self, value: int):
        self.value: int = int(value)

class String(Node):
    def __init__(self, value: str):
        self.value: str = str(value)

class BinOp(Node):
    def __init__(self, left, right, op):
        self.left = left
        self.right = right
        self.op = op

def parse(tokens):
    stack = []
    for token in tokens:
        if token.isdigit():
            stack.append(Number(token))
        elif token[0] == '"' and token[len(token) - 1] == '"':
            stack.append(String(token[1:len(token) - 1]))
        else:
            right = stack.pop()
            left = stack.pop()
            stack.append(BinOp(left, right, token))
    return stack[len(stack) - 1]

binding.initialize()
binding.initialize_native_target()
binding.initialize_native_asmprinter()

class LLVMCodeGen:
    def __init__(self):
        self.module = ir.Module(name="stack")
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
        elif isinstance(node, String):
            text = ir.GlobalVariable(self.module, ir.ArrayType(ir.IntType(8), len(node.value)), name="str")
            text.initializer = ir.Constant(ir.ArrayType(ir.IntType(8), len(node.value)), bytearray(f"{node.value}\0", "utf-8"))
            text.global_constant = True
            return text
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

def compile_ir(ir_code):
    target = llvm.Target.from_default_triple()
    target_machine = target.create_target_machine()
    backing_mod = llvm.parse_assembly(ir_code)
    engine = llvm.create_mcjit_compiler(backing_mod, target_machine)

    engine.finalize_object()
    engine.run_static_constructors()
    return engine

print("Stack Compiler")
while True:
    codegen = LLVMCodeGen()
    expression = input("> ")
    tokens = tokenize(expression)
    ast = parse(tokens)
    llvm_ir = codegen.generate_code(ast)
    print(llvm_ir)

    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    engine = compile_ir(llvm_ir)
    main_ptr = engine.get_function_address("main")

    main_func = ctypes.CFUNCTYPE(ctypes.c_int32)(main_ptr)
    print("Result:", main_func())
