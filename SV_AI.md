<!-- toc-start -->

# 目录

[1. \[SystemVerilog语法拾遗\] SystemVerilog中的宏使用详解](#1-systemverilog语法拾遗-systemverilog中的宏使用详解)  
　　[1.1 引言](#11-引言)  
　　[1.2 前言](#12-前言)  
　　[1.3 介绍](#13-介绍)  
　　　　[1.3.1 什么是宏？](#131-什么是宏)  
　　　　[1.3.2 为什么要使用宏？](#132-为什么要使用宏)  
　　[1.4 宏语法规范](#14-宏语法规范)  
　　　　[1.4.1 宏名称](#141-宏名称)  
　　　　[1.4.2 反引号——*``` ``, `", `\`" ```*](#142-反引号)  
　　　　[1.4.3 其他应用](#143-其他应用)  
　　[1.5 传递参数](#15-传递参数)  
　　[1.6 宏风格指引](#16-宏风格指引)  
　　[1.7 参考示例](#17-参考示例)  
　　[1.8 总结](#18-总结)  
　　[1.9 疑问与评论](#19-疑问与评论)  
　　　　[1.9.1 补充](#191-补充)  

<!-- toc-end -->

---

# 1. [SystemVerilog语法拾遗] SystemVerilog中的宏使用详解

> 来源：https://zhuanlan.zhihu.com/p/660094987
> 发布时间：2023-10-08T08:51:51.000Z
> update 2026/08/22 11 : 12

## 1.1 引言

刚刚写了一篇 [数字验证大头兵：[SystemVerilog语法拾遗] 宏函数实例讲解](https://zhuanlan.zhihu.com/p/660080798)，本想着过一段时间再好好研究研究宏函数的语法再写一篇详细点的解析文档，奈何求知欲过于强烈的我还是决定现在就好好研究下宏函数的语法，正巧看到一篇写的不错的宏函数讲解文章，这里就用我有限的英文翻译水平加之对宏函数的一点理解共享给大家，原文链接如下：[SystemVerilog Macros - SystemVerilog.io](https://link.zhihu.com/?target=https%3A//www.systemverilog.io/verification/macros/)

下面是全文翻译

## 1.2 前言

合理的使用宏可以大大简化我们在使用SystemVerilog编写代码的工作量，如果你不熟悉宏的使用，不仅降低写代码的效率，同时在阅读别人写的代码时也会产生诸多困惑，这里的例子将揭开`` `, `", `\`" ``这些宏中常用的符号的含义以及如何使用它们的神秘面纱。

我们还将探索UVM源代码中的一些宏，并建立编写宏的风格指南。

在我们开始之前有一个警告：过度使用宏可能会导致代码可读性降低，所以使用宏一定要尽可能的再简化代码的前提下不要因为对代码的过度封装而影响其可读性。

本文中涉及到的所有代码示例都可以从下面的链接下载使用：[All code presented here can be downloaded from GitHub](https://link.zhihu.com/?target=https%3A//github.com/subbdue/systemverilog.io)

## 1.3 介绍

### 1.3.1 什么是宏？

宏是使用`define编译器指令创建的代码段。它们主要包含三部分：名称、文本和可选参数，如下所示。

```
`define macroname(ARGS) macrotext
```

在编译预处理阶段，代码中每次出现`macroname都会替换为字符串macrotext，ARGS是可以在macrotext中使用的变量。

### 1.3.2 为什么要使用宏？

在编写测试平台和测试用例时，有时候会重复使用某些代码段，如下所示。

```
//1
for (int ii=0; ii<numbytes; ii++) begin
    if ((ii !=0) && (ii % 16 == 0))
        $display("\n");
    $display("0x%x ", bytearray[ii]);
end
//2
for (int ii=20; ii<100; ii++) begin
    if (ii % 16 == 0)
        $display("\n");
    $display("0x%x ", pkt[ii]);
end
```

代码段1和2有着高度的相似性，我们可以从中提取公共部分辅之以参数化的形式将其抽象成如下所示的宏，从而大大简化了代码量，并且后期如果需要更改其中的打印控制只需修改一处就可以了。

```
`define print_bytes(ARR, STARTBYTE, NUMBYTES) \
    for (int ii=STARTBYTE; ii<STARTBYTE+NUMBYTES; ii++) begin
        if ((ii != 0) && (ii % 16 == 0))
            $display("\n");
        $display("0x%x ", ARR[ii]);
    end

// When someone reads this code, they'll know
// it prints a formatted array of bytes
`print_bytes(bytearray, 0, numbytes)
`print_bytes(pkt, 20, 80)
```

我喜欢使用宏，尤其是用于特殊的打印功能，而`uvm\_info是不够的。如果您的所有团队成员都使用这个宏，那么就统一了团队的打印风格，这样使得每个人都更容易阅读log信息。

以下是使用宏的推荐方法：

- 您和您的团队可以建立一个宏库
- 对此库中的宏使用特定的命名规则，例如<\*>\_utils（print\_byte\_utils等）。
- 将其放入名为macro\_utils.sv的文件中，并将其包含在一个公共包中
- 在设计/验证需要的场景中导入这个宏文件，避免重复造轮子的情况

以上便是宏存在的价值。

## 1.4 宏语法规范

### 1.4.1 宏名称

宏名称的唯一规则是，除编译器指令外，您可以使用任何名称，即不能使用关键字，如“define”、“ifdef”、“endif”、“else”、”elseif“、”include“等。如果你最终错误地使用了编译器指令，你会得到如下错误提示。

```
Mentor Graphics Questa

----------------------
    ** Error: macros_one.sv(4): (vlog-2264) Cannot redefine compiler
directives
:
    `include.

Synopsys VCS
------------
    Error-[IUCD] Illegal use of compiler directive
      Illegal use of compiler directive: `include is illegal in this context.
      "macros_one.sv", 28
      Source info:         $display(`include(clock));
```

此外，宏的作用域为“全局”的，宏的使用只跟编译顺序有关，一旦在某个某件中定义了宏，随后编译的文件中都可以使用这个宏，不管这个宏是定义在在类内还是在类外。一旦编译器获取了一个定义，它就可以在任何地方使用。如果你重新定义宏，你会得到如下错误提示。

```
** Warning: macros2.sv(7): (vlog-2263) Redefinition of macro:
    'debug' (previously defined near macros2.sv(3)) .

    Parsing design file 'macros4.sv'

    Warning-[TMR] Text macro redefined
    macros2.sv, 7
      Text macro (debug) is
redefined
. The last definition will override previous
      ones.
      In macros2.sv, 3, it was defined as $display("%s, %0d: %s", `__FILE__,
      `__LINE__, msg)
```

### 1.4.2 反引号——*``` ``, `", `\`" ```*

常用的符号主要有三类。

**1、反引号和双引号 `"**

如果宏文本用纯引号“ 括起来，它本质上就是一个字符串。双引号内的参数不会被替换，如果宏文本嵌入了其他宏，它们也不会展开。如果在双引号前面加一个反引号`，那么双引号的意义就被替换了，使得宏在展开时需要遵循以下原则：

- 包含双引号`"与`"
- 两个双引号内的参数需要被替换
- 两个双引号内嵌入的宏都应该展开

我们看下面这个例子

```
/* Example 1.1 */
`define append_front_bad(MOD) "MOD.master"
`define append_front_good(MOD) `"MOD.master`"

program automatic test;
    initial begin
        $display(`append_front_bad(clock1));
        $display(`append_front_good(clock1));
    end
endprogram: test
```

运行结果如下所示

```
CONSOLE OUTPUT
# MOD.master
# clock1.master
```

``append_front_bad`——接受一个参数MOD，期望宏将两个字符串（MOD和“.master”）串联起来，但由于使用了双引号，输出结果为字符串“MOD.master”，参数并未被替换。

``append_front_good`——这是`append\_front\_bad的正确版本。通过在双引号前使用反引号，进而告诉编译器，当宏展开时，需要替换参数MOD。

**2、双反引号 ``**

本质上是一个标记分隔符，它有助于编译器清楚地区分参数和宏文本中字符串的其余部分，可以用在需要分隔的字符串前面或者后面来对字符串做分隔。

参考如下的代码例子

```
/* Example 1.2 */
`define append_front_2a(MOD) `"MOD.master`"
`define append_front_2b(MOD) `"MOD master`"
`define append_front_2c_bad(MOD) `"MOD_master`"
`define append_front_2c_good(MOD) `"MOD``_master`"
`define append_middle(MOD) `"top_``MOD``_master`"
`define append_end(MOD) `"top_``MOD`"
`define append_front_3(MOD) `"MOD``.master`"

program automatic test;
    initial begin
        /* Example 1.2 */
        $display(`append_front_2a(clock2a));
        $display(`append_front_2b(clock2b));
        $display(`append_front_2c_bad(clock2c));
        $display(`append_front_2c_good(clock2c));
        $display(`append_front_3(clock3));
        $display(`append_middle(clock4));
        $display(`append_end(clock5));
    end
endprogram: test
```

运行结果如下所示

```
CONSOLE OUTPUT
    # clock2a.master
    # clock2b master
    # MOD_master
    # clock2c_master
    # clock3.master
    # top_clock4_master
    # top_clock5
```

``append_front_2a`和2b——**空格和句点都是自然的标记分隔符**，即编译器可以清楚地识别宏文本中的参数\_2a在参数MOD和字符串master之间使用“句点”\_2b在参数MOD和字符串master之间使用了一个“空格”，。

``append_front_2c_bad`——如果参数附加了**非空格**或**非句点**字符，例如“MOD\_master`”中的**下划线（\_）**，则编译器无法确定参数字符串MOD的结束位置，因而就**不会对MOD进行替换而将MOD\_master作为一个整体进行解析**。

``append_front_2c_good`——**双反引号``在MOD和\_master之间创建了一个分隔符**，这就是为什么MOD被正确识别和替换的原因`append\_middle和`append\_end是另外两个例子。

``append_front_3`——在自然标记分隔符（即空格或句点）之前或之后放置“”是可以的，但属于冗余操作。

**3、反引号、反斜杠和双引号 `\`"**

宏展开时会解析为 `"` ，如果需要嵌套的使用双引号，可以使用此选项，代码示例如下

```
/* Example 1.3 */
`define complex_string(ARG1, ARG2) \
    `"This `\`"Blue``ARG1`\`" is Really `\`"ARG2`\`"`"

program automatic test;
    initial begin
        $display(`complex_string(Beast, Black));
    end
endprogram: test
```

运行结果如下

```
CONSOLE OUTPUT
    # This "BlueBeast" is Really "Black"
```

如果以上这些例子还不足以解释清除这几个符号的意义的话，还可以通过下面的链接下载更多的实例：[Download the example code from this section](https://link.zhihu.com/?target=https%3A//github.com/subbdue/systemverilog.io/tree/master/macros)

### 1.4.3 其他应用

- 嵌套使用宏
- 宏中也可以使用注释
- 宏中也可以使用`ifdefs` 这类宏

## 1.5 传递参数

在使用宏参数时以下几点需要铭记于心：

- 参数允许有缺省值。
- 您可以通过将该位置留空来跳过参数，即使它没有缺省值（这一点跟函数/任务调用不同），下面的代码示例中`test2(,,)打印结果验证无缺省值的变量参数空缺时宏会把它替换为空字符。
- 观察下免示例中的`debug1和`debug2这两个宏，如果参数是字符串，则是否需要将参数用双引号括起来取决于参数在宏文本中的替换位置。在`debug1中，MODNAME位于宏文本的引号内，因此在调用宏时，我没有用引号括起字符串`program-block`。而对于`debug2，传递的参数是用引号括起来的`“program-block”`，因为MODNAME出现在宏文本的引号外。

代码示例如下

```
/* Example 2 */
`define test1(A) $display(`"1 Color A`")
`define test2(A=blue, B, C=green) $display(`"3 Colors A, B, C`")
`define test3(A=str1, B, C=green) \
    if (A == "orange")$display("Oooo .. I received an Orange!"); \
    else $display(`"3 Colors %s, B, C`", A);

`define debug1(MODNAME, MSG) \
    $display(`" ``MODNAME`` >> %s, %0d: %s`", `__FILE__, `__LINE__, MSG)
`define debug2(MODNAME, MSG) \
    $display(`"%s >> %s, %0d: %s`", MODNAME, `__FILE__, `__LINE__, MSG)

program automatic test;
    initial begin
        string str1, str2;
        str1 = "gray";
        str2 = "orange";

        // No args provided even without default value
        `test1();
        `test2(,,);

        // Passing some args
        `test1(black);
        `test2(,pink,);

        // Passing a var (str1, str2) as an arg
        `test3(str1,mistygreen,babypink);
        `test3(str2,mistygreen,babypink);

        `debug1(program-block, "this is a debug message");
        `debug2("program-block", "this is a debug message");

        /* The following will result in an Error
        * `test2(); // no args provided
        * `test2(,); // insufficient args provided
        *
        * // arg1 is used as a var in an if statement,
        * // This will compile fail because the macro
        * // will expand to *if ( == "orange")*
        * `test(, blue, pink)
        */
    end
endprogram: test
```

运行结果如下

```
CONSOLE OUTPUT

    # 1 Color
    # 3 Colors blue, , green
    # 1 Color black
    # 3 Colors blue, pink, green
    # 3 Colors gray, mistygreen, babypink
    # Oooo .. I received an Orange!
    #  program-block >> macros2.sv, 31: this is a debug message
    # program-block >> macros2.sv, 32: this is a debug message
```

## 1.6 宏风格指引

在整个团队中遵循一致的宏命名风格是非常有用的。由于UVM现在被广泛用作验证方法，我们可以从他们的源代码中借用一段，并使用他们宏编码风格。如果您查看UVM库的源代码，您将看到以下内容：

- 如果宏定义函数或任务，请使用大写宏名称和小写参数名称
- 如果宏定义了类、代码段等内容，请使用小写宏名称和大写作为参数
- 用下划线分隔宏名称中的单词

在下一节中，我从UVM库中挑选了一些宏，它们很好的彰显了上述命名规则。

## 1.7 参考示例

通常，你只需要看一堆例子便可以刷新你对如何使用宏的认知，下面是我从UVM库的源代码中挑选的一些示例，你应该能够从我们上面讲解的内容中很好的理解这些示例。

```
//> src/base/uvm_phase.svh
`define UVM_PH_TRACE(ID,MSG,PH,VERB) \
   `uvm_info(ID, {$sformatf("Phase '%0s' (id=%0d) ", \
       PH.get_full_name(), PH.get_inst_id()),MSG}, VERB);

//> src/macros/uvm_tlm_defines.svh
// Check out the MacroStyleGuide in use here
// [ 1.] If the Macro defines a function or a task,
// use UPPERCASE for macro name and lower case for args
`define UVM_BLOCKING_TRANSPORT_IMP_SFX(SFX, imp, REQ, RSP, req_arg, rsp_arg) \
  task transport( input REQ req_arg, output RSP rsp_arg); \
    imp.transport``SFX(req_arg, rsp_arg); \
  endtask

// [ 2a.] For everything else (i.e., if Macro defines
// a snippet of code, class or a convenience definition),
// use lowercase with UPPERCASE args
`define uvm_analysis_imp_decl(SFX) \
    class uvm_analysis_imp``SFX #(type T=int, type IMP=int) \
      extends uvm_port_base #(uvm_tlm_if_base #(T,T)); \
      `UVM_IMP_COMMON(`UVM_TLM_ANALYSIS_MASK,`"uvm_analysis_imp``SFX`",IMP) \
      function void write( input T t); \
        m_imp.write``SFX( t); \
      endfunction \
      \
    endclass

// [ 2b.] Examples of lowercase+uppercase with snippets
`define uvm_error(ID, MSG) \
   begin \
     if (uvm_report_enabled(UVM_NONE,UVM_ERROR,ID)) \
       uvm_report_error (ID, MSG, UVM_NONE, `uvm_file, `uvm_line, "", 1); \
   end
// [ 3.] Separate words with underscores, don't use camelCase
`define uvm_non_blocking_transport_imp_decl(SFX) \
    `
uvm
_nonblocking_transport_imp_decl(SFX)

//> src/macros/uvm_sequence_defines.svh
`define uvm_do(SEQ_OR_ITEM) \
  `uvm_do_on_pri_with(SEQ_OR_ITEM, m_sequencer, -1, {})

`define uvm_do_with(SEQ_OR_ITEM, CONSTRAINTS) \
  `uvm_do_on_pri_with(SEQ_OR_ITEM, m_sequencer, -1, CONSTRAINTS)

 `define uvm_do_on_pri_with(SEQ_OR_ITEM, SEQR, PRIORITY, CONSTRAINTS) \
  begin \
  uvm_sequence_base __seq; \
  `uvm_create_on(SEQ_OR_ITEM, SEQR) \
  if (!$cast(__seq,SEQ_OR_ITEM)) start_item(SEQ_OR_ITEM, PRIORITY);\
  if ((__seq == null || !__seq.do_not_randomize) && !SEQ_OR_ITEM.randomize() with CONSTRAINTS ) begin \
    `uvm_warning("RNDFLD", "Randomization failed in uvm_do_with action") \
  end\
  if (!$cast(__seq,SEQ_OR_ITEM)) finish_item(SEQ_OR_ITEM, PRIORITY); \
  else __seq.start(SEQR, this, PRIORITY, 0); \
  end

`define uvm_create_on(SEQ_OR_ITEM, SEQR) \
  begin \
  uvm_object_wrapper w_; \
  w_ = SEQ_OR_ITEM.get_type(); \
  $cast(SEQ_OR_ITEM , create_item(w_, SEQR, `"SEQ_OR_ITEM`"));\
  end
```

## 1.8 总结

- 遵循统一的宏编码风格，确保整个团队的一致性

- 函数和任务的大写宏名称和小写参数
- 用下划线分隔单词
- 其他所有内容（如类、代码片段等）的小写宏名称和大写参数
- 使用宏时要谨慎，过度使用可能会导致代码可读性变差

- 知道何时使用以下符号 `"、`` 和 `\`"
- 宏强制在全局命名空间有效，在类中定义宏并不意味着它只对该类可见。
- 注意编译log中的宏重新定义的警告
- 编写宏时，请使用本文中的示例作为参考

## 1.9 疑问与评论

可以通过如下链接与作者进行交流讨论：[please use this GitHub Discussions link](https://link.zhihu.com/?target=https%3A//github.com/subbdue/systemverilog.io/discussions/9)

### 1.9.1 补充

如果想要在字符串中嵌套宏，可以借助反引号`完成，如下图所示：

![](SV_AI_assets/image-0001.jpg)
