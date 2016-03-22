<h3>Django源码阅读笔记</h3></br>
>一开始是想写几篇博客，但是中间好像要描述不少代码，于是还是推github吧😄</br>
还是采用先代码＋注释的形式，最后再用博客来做总结.

----------03.21更新-----------
>django的wsgi模块，有一个需要注意的是middleware的使用。</br>
所谓middleware，翻译过来就是中间件。</br>
在django源码中，BaseHandler类中的get_response方法有一个循环调用中间件的request处理函数，直到有response返回，循环终止.</br>
中间件到底是用来干什么的.
这里我们举个例子，中间件最外层的是一个common中间件，它是用来分析url的格式的，比如如果开头没有www，就给它加上www,结尾该有斜线却没斜线，就给它加上斜线，最后一步，实现跳转，跳转到你填充后新得到的url那里去，这个redirect就作为一个response返回了.</br>
但是如果不需要跳转，url本身就很完美了，common中间件什么也不返回，于是我们就要往下走，看看下一个中间件会返回给我们什么</br>
以此类推，一直走下去，到有response返回为止</br>
获取了response，还没完，还要调用响应中间件，响应中间件用于执行了view函数之后，对返回中的response进行一些操作</br>
响应中间件是各种中间件的process_response函数的集合，我们照样是用for语句去循环调用它，不同的是，调用顺序是自下网上，与请求中间件的调用顺序相反，哈哈</br>
一图胜千言</br>

![middleware机制](http://7xl4oh.com1.z0.glb.clouddn.com/django-middleware.jpg)
