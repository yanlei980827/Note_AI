开发一个提取指定连接的微信文章到 markdown 的 app，该项目的代码都放在extract_wechat_article 目录下面。

app具体要求如下：

1. 在 windows 10 上运行
2. app 界面可以指定微信文章链接
3. app 界面可以指定 markdown 的路径
4. 可以将微信文章的图片也都提取到 markdown 中
5. 可以在已有 markdown 后面进行续写，即将提取的新的微信文章续写到已有的 markdown 文件的后面

将发布时间改为提取时间，引用块里把提取时间加上，格式为 update year/month/day；并且软件里加上打开 markdown 的按钮；



查看当前目录下的 test 目录下的 test.md，里面有两篇文章。基于 ICG + 三级同步电路的无毛刺时钟切换方案 是第一篇文章；83：后向寄存器切片（backword register slice）是第二篇文章。提取第二篇文章的时候 markdown 格式混乱。修改下这个 bug。并且提取到 markdown 的时候把提取时间加上。



图片保存在和 markdown 相同目录下，文件夹的名字为 markdown的对应文件名_assets。并且如果是在已有 markdown 文件的基础上进行续写，新文章的图片索引在原来基础上进行累加，而不是从0开始。修复这个 bug 并重新生成 exe

你并没有根据 markdown文件名生成对应的 assets 文件夹。比如目前 markdown 文件名为 test，你应该生成 test_assets 文件夹



