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

class FuncCall(Node):
    def __init__(self, name, args):
        self.name = name
        self.args = args

def parse(tokens):
    stack = []
    for token in tokens:
        if token == "":
            continue
        if token.isdigit():
            stack.append(Number(token))
        elif token[0] == '"' and token[len(token) - 1] == '"':
            stack.append(String(token[1:len(token) - 1]))
        elif token in ["add", "sub", "mul", "div"]:
            right = stack.pop()
            left = stack.pop()
            stack.append(BinOp(left, right, token))
        elif token == "println":
            args = stack.pop()
            stack.append(FuncCall("puts", args))
    return stack

binding.initialize()
binding.initialize_native_target()
binding.initialize_native_asmprinter()

class LLVMCodeGen:
    def __init__(self):
        self.module = ir.Module(name="stack")
        self.builder = None
        self.func = None
        self.puts = None
        self.block = None
        self.str_count = 0

    def generate_code(self, nodes):
        self.func = ir.Function(self.module, ir.FunctionType(ir.IntType(32), ()), name="main")
        self.block = self.func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(self.block)

        puts_ty = ir.FunctionType(ir.IntType(32), [ir.PointerType(ir.IntType(8))], var_arg=False)
        self.puts = ir.Function(self.module, puts_ty, name="puts")

        result = None
        for node in nodes:
            result = self.codegen(node)

        self.builder.ret(result)
        return str(self.module)

    def codegen(self, node):
        if isinstance(node, Number):
            return ir.Constant(ir.IntType(32), node.value)
        elif isinstance(node, String):
            text = ir.GlobalVariable(self.module, ir.ArrayType(ir.IntType(8), len(node.value) + 1), name=f"str{self.str_count}")
            text.initializer = ir.Constant(ir.ArrayType(ir.IntType(8), len(node.value) + 1), bytearray(f"{node.value}\0", "utf-8"))
            text.global_constant = True; self.str_count += 1
            return text
        elif isinstance(node, FuncCall):
            addr = self.builder.bitcast(self.codegen(node.args), ir.PointerType(ir.IntType(8)))
            return self.builder.call(self.puts, [addr])
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
    ast =  parse(tokens)

    llvm_ir = codegen.generate_code(ast)
    print(llvm_ir)

    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    engine = compile_ir(llvm_ir)
    main_ptr = engine.get_function_address("main")

    main_func = ctypes.CFUNCTYPE(ctypes.c_int32)(main_ptr)
    print("Result:", main_func())
