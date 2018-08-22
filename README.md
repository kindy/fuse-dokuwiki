# [FUSE DokuWiki](https://git.io/fNDtm)

将 DokuWiki 的 wiki 使用 fuse 挂载到本地，然后可以使用本地编辑器编辑。

dokuwiki 必须启用了 markdown 插件，并且启用了 xmlrpc 功能。


## 用法

python main.py -s http://dokuwiki.com:80 -u abc -p '' ./mount-dir/
```

当指定了 `-p ''` 时，会询问密码。
