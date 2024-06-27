#基于vsphere 6.7 使用Python 3.10用于简单快速管理vSphere 环境中主机和虚拟机
主要以快速获取宿主机以及虚拟机相关信息，对虚拟机快速查看、创建快照、开关虚拟机、删除虚拟机为主，打包成exe后单独执行

安装环境：
  需要的库：atexit、ssl、time、itertools、pyVim.connect、pyVmomi、tkinter

问题：
  1、多个快照获取存在缺少部分快照信息
  2、宿主机开机功能尚未完成
