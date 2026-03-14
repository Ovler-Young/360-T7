云编译7981固件
（p3terx 2024新版 基于ubuntu22.04）

360T7 / JCG Q30 PRO 主路由固件，含 DDNS 等模块（用最新源码编译）。

CMCC-A10(ZN-M5) 极简AP固件。


237大佬源码网址:
[[https://github.com/padavanonly/immortalwrt-mt798x-24.10](https://github.com/padavanonly/immortalwrt-mt798x-6.6)]

【24.10 版本强烈推荐 6.6内核！各方面表现都优于 5.4内核。5.4技术过于老旧。】  
【24.10 6.6内核的源码要改 a10-stock dts 代码才能在h大uboot下正常启动，详见 https://github.com/ATang007ZH/immortalwrt-mt798x-6.6 改动】


使用p3terx云编译模板
**English** | [中文](https://p3terx.com/archives/build-openwrt-with-github-actions.html)

----------------------------------------------------------------
config配置文件，建议采用本地生成。可装linux或者Windows下装wsl，按照官方编译步骤操作。

----------------------------------------------------------------
注意，新建的repositories ，要修改权限（原来只读，改成读写权限）。

Settings，Actions，General，右侧栏拉到最下面，	Workflow permissions，勾选 Read and write permissions

----------------------------------------------------------------
更新刷写固件时，跨版本更新的，记得不要保存设置。

刷写完新固件后，记得先清理浏览器缓存，再访问路由器进行设置。
