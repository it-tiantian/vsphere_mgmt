import atexit
from itertools import count
import ssl
import time
import socket
from pyVim.connect import Disconnect, SmartConnect
from pyVmomi import vim, vmodl
import tkinter as tk
from tkinter import messagebox

# 磁盘大小来显示不同的单位（例如字节、千字节、兆字节、吉字节等
def format_disk_size(bytes):
    if bytes < 1024:
        return f"{bytes} 字节"
    elif bytes < 1024 * 1024:
        kilobytes = bytes / 1024
        return f"{kilobytes:.2f} KB"
    elif bytes < 1024 * 1024 * 1024:
        megabytes = bytes / (1024 * 1024)
        return f"{megabytes:.2f} MB"
    elif bytes < 1024 * 1024 * 1024 * 1024:
        gigabytes = bytes / (1024 * 1024 * 1024)
        return f"{gigabytes:.2f} GB"
    else:
        terabytes = bytes / (1024 * 1024 * 1024 * 1024)
        return f"{terabytes:.2f} TB"
    
# 时间
def format_time(seconds):
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}分钟"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}小时"
    else:
        days = seconds // 86400
        return f"{days}天"
    
# 根据 CPU 大小来显示不同的单位（例如赫兹、千赫兹、兆赫兹等）
def format_cpu_speed(hertz):
    if hertz < 1000:
        return f"{hertz} Hz"
    elif hertz < 1000000:
        kilohertz = hertz / 1000
        return f"{kilohertz:.2f} kHz"
    elif hertz < 1000000000:
        megahertz = hertz / 1000000
        return f"{megahertz:.2f} MHz"
    else:
        gigahertz = hertz / 1000000000
        return f"{gigahertz:.2f} GHz"
    
# 根据内存大小来显示不同的单位（例如字节、千字节、兆字节、吉字节等）
def format_memory_size(bytes):
    if bytes < 1024:
        return f"{bytes} 字节"
    elif bytes < 1024 * 1024:
        kilobytes = bytes / 1024
        return f"{kilobytes:.2f} KB"
    elif bytes < 1024 * 1024 * 1024:
        megabytes = bytes / (1024 * 1024)
        return f"{megabytes:.2f} MB"
    else:
        gigabytes = bytes / (1024 * 1024 * 1024)
        return f"{gigabytes:.2f} GB"
    
# 虚拟机开关机需要的一个方法
def WaitForTasks(service_instance, tasks):
    """
    Given the service instance si and tasks, it returns after all the
    tasks are complete
    """
    pc = service_instance.content.propertyCollector
    task_list = [str(task) for task in tasks]
    # Create filter
    obj_specs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task)
                 for task in tasks]
    property_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                             pathSet=[],
                                                             all=True)
    filter_spec = vmodl.query.PropertyCollector.FilterSpec()
    filter_spec.objectSet = obj_specs
    filter_spec.propSet = [property_spec]
    pcfilter = pc.CreateFilter(filter_spec, True)
    try:
        version, state = None, None
        # Loop looking for updates till the state moves to a completed state.
        while True:
            update = pc.WaitForUpdates(version)
            for filter_set in update.filterSet:
                for obj_set in filter_set.objectSet:
                    task = obj_set.obj
                    for change in obj_set.changeSet:
                        if change.name == 'info':
                            state = change.val.state
                        elif change.name == 'info.state':
                            state = change.val
                        else:
                            continue

            # Check if the state moved to a completed state.
            if state == vim.TaskInfo.State.success:
                return task.info.result
            elif state == vim.TaskInfo.State.error:
                raise task.info.error
    finally:
        if pcfilter:
            pcfilter.Destroy()

# 与vsphere建立连接
def connect_vsphere(host,user,password,port):
    context = None
    # 建立与vSphere的连接
    if hasattr(ssl, '_create_unverified_context'):
        context = ssl._create_unverified_context()
    try:
        si = SmartConnect(host=host,user=user,pwd=password,port=port,sslContext=context)
        atexit.register(Disconnect, si)
        return si
    except vim.fault.InvalidLogin as e:
        tk.messagebox.showerror('错误',str(e.msg))
    except Exception as e:
        tk.messagebox.showerror('错误',str(e))

# 处理虚拟机快照嵌套
def _get_snapshot_info(snapshot):
    """
    递归获取快照信息
    :return: 包含所有快照信息的字符串，包含快照的名称、描述、创建时间等信息
    """
    snapshot_time = snapshot.createTime.strftime("%Y年%m月%d日 %H:%M:%S")
    message = f"虚拟机名:{snapshot.vm} 状态:{snapshot.state} 快照ID:{snapshot.id} 创建时间:{snapshot_time} 快照名:{snapshot.name} 快照说明:{snapshot.description}  \n"
    return message

class get_info(object):
 
    def get_host_name(si):
        """  获取虚拟主机名称和状态"""
        content = si.RetrieveContent()
        obj =  content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True).view
        hostname = []
        for vmhost in obj:
            hostinfo = {}
            hostinfo.update({
                "hostname":vmhost.name,
                "powerstate":vmhost.runtime.powerState,
                })
            hostname.append(hostinfo)
        return hostname
  
    # 获取物理机详情
    def get_host_template(si,host_name):
        """ 获取vsphere主机详细信息 """
        content = si.RetrieveContent()
        search_index = content.searchIndex
        host = search_index.FindByDnsName(dnsName=host_name, vmSearch=False)
        host_information = {}

        if host:
            # 获取物理机电源状态
            power_state = host.runtime.powerState
            if power_state == "poweredOn":
                host_information['status'] = "开机"
                vm_name = []
                # 获取物理机信息
                cpu_usage = host.summary.quickStats.overallCpuUsage
                total_cpu_resource = host.summary.hardware.numCpuCores * host.summary.hardware.cpuMhz
                total_memory = host.hardware.memorySize
                memory_usage = host.summary.quickStats.overallMemoryUsage 
                uptime = host.summary.quickStats.uptime
                # 获取存储信息
                total_storage_size = 0
                # 获取存储已用信息
                used_storage_size = 0
                for datastore in host.datastore:
                    total_storage_size += datastore.summary.capacity
                    # 检查每个存储设备的已用容量
                    used_storage_size += datastore.summary.capacity - datastore.summary.freeSpace
                # 转换存储大小为 GB 或 TB，视情况而定
                total_storage_size_in_gb = total_storage_size  # 转换为 GB
                used_storage_size_in_gb = used_storage_size  # 转换为 TB
                # 内存可用
                memAvailable = total_memory - (memory_usage * 1024 * 1024)
                # print(format_memory_size(memAvailable))
                # 磁盘可用
                storageAvailable = total_storage_size_in_gb - used_storage_size_in_gb
                # cpu可用
                cpuAvailable = total_cpu_resource - cpu_usage
                # get vm name
                for i in host.vm:
                    vm_name.append(i.name)

                host_information.update({
                    "name": host.name,
                    "hardware_model": host.hardware.systemInfo.model,
                    "cpu_model": host.hardware.cpuPkg[0].description,
                    "cpu_cores": host.hardware.cpuInfo.numCpuCores,
                    "cpu_sockets": host.hardware.cpuInfo.numCpuPackages,
                    "cpu_available":format_cpu_speed(cpuAvailable * 1000000),
                    "物理机逻辑处理器数量": host.summary.hardware.numCpuThreads,
                    "物理机 CPU 使用情况": format_cpu_speed(cpu_usage * 1000000 ),
                    "物理机总 CPU 资源": format_cpu_speed(total_cpu_resource * 1000000 ),
                    "物理机总内存": format_memory_size(total_memory),
                    "物理机内存使用情况": format_memory_size(memory_usage * (1024 * 1024) ),
                    "mem_available":format_memory_size(memAvailable),
                    "物理机总运行时长": format_time(uptime),
                    "物理机总存储空间大小": format_disk_size(total_storage_size_in_gb),
                    "物理机存储已用大小": format_disk_size(used_storage_size_in_gb),
                    "storage_available":format_disk_size(storageAvailable),
                    "VM":vm_name,
                })
            else:
                host_information['status'] = "关机"
                host_information['name'] = host.name
        return host_information

    # 虚拟机简略信息
    def get_vm_template(si):
        """ 获取所有虚拟机的名称 IP 操作系统  CPU  内存 状态 所属物理机 """
        content = si.RetrieveContent()
        container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        vms = container.view
        vm_list = []
        
        for vm in vms:
            #print(vm)
            vm_information = {}
            vm_information.update({
                "vmname": vm.name,
                "status":vm.runtime.powerState,
                "ip":format(vm.guest.ipAddress),
                "vmpath":format(vm.config.files.vmPathName),
                "system":format(vm.config.guestFullName),
                "mem":format(format_memory_size(vm.config.hardware.memoryMB * 1024 * 1024)),
                "vspherehost":format(vm.runtime.host.name),
            })
            vm_list.append(vm_information)
        return vm_list

    # 虚拟机详细信息
    def get_vm_details(si, vm_name):
        """ 获取指定虚拟机的详细信息 """
        content = si.RetrieveContent()
        container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        vms = container.view

        total_disk_capacity_gb = 0
        total_disk_free_gb = 0
        disk_block = 0

        vm_information = {}
        disk_data = {}
        disk_data2 = []
        for vm in vms:
            if vm.name == vm_name:
                vm_state = vm.runtime.powerState
                if vm_state == "poweredOn":
                    vm_information['status'] = "开机"
                else:
                    vm_information['status'] = "关机"
                vm_information.update({
                    "name" : vm.name,
                    "IP" : vm.guest.ipAddress,
                    "system" : vm.config.guestFullName,
                    "cpu核数" : vm.config.hardware.numCPU,
                    "mem": format_memory_size(vm.config.hardware.memoryMB * 1024 * 1024),
                    "host":vm.runtime.host.name,
                    "cpu 使用":format_cpu_speed(vm.summary.quickStats.overallCpuUsage * 1000000),
                    "mem使用": format_memory_size(vm.summary.quickStats.guestMemoryUsage * 1024 * 1024 ),
                })
                # 磁盘类型
                for device in vm.config.hardware.device:
                    if isinstance(device, vim.vm.device.VirtualDisk):
                        disk_capacity_kb = device.capacityInKB
                        total_disk_capacity_gb += disk_capacity_kb
                        # 硬盘块数统计
                        disk_block += 1
                        vm_information['硬盘块'] = disk_block
                        vm_information['总储存'] = format_disk_size(total_disk_capacity_gb * 1024)

                        # 硬盘详细情况                        
                        if isinstance(device.backing, vim.vm.device.VirtualDisk.FlatVer2BackingInfo):
                            if device.backing.thinProvisioned == True:
                                disk_data2.append({"disk名称" : device.deviceInfo.label,'disk大小':format_disk_size(disk_capacity_kb * 1024),"disk类型": "精简置备"})
                            else:
                                if device.backing.eagerlyScrub == None:
                                    disk_data2.append({"disk名称" : device.deviceInfo.label,'disk大小':format_disk_size(disk_capacity_kb * 1024),"disk类型": "厚置备延迟置零"})
                                elif device.backing.eagerlyScrub == True:
                                    disk_data2.append({"disk名称" : device.deviceInfo.label,'disk大小':format_disk_size(disk_capacity_kb * 1024),"disk类型": "厚置备快速置零"})
                vm_information['disk'] = disk_data2

        return vm_information

    #虚拟机快照信息
    def get_vm_snapshot(si, vm_name):
        """ 获取指定虚拟机的快照信息 """
        try:
            content = si.RetrieveContent()
            container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
            for c in container.view:
                if c.name == vm_name:
                    snapshots = c.snapshot.rootSnapshotList
                    messages =''
                    if snapshots != None:
                        if len(snapshots) >=1 :
                            for snapshot in snapshots:
                                messages += _get_snapshot_info(snapshot)
                                if len(snapshot.childSnapshotList) >=1 :
                                    for i in snapshot.childSnapshotList:
                                        messages += _get_snapshot_info(i)
                                        if len(i.childSnapshotList) >=1 :
                                            for y in i.childSnapshotList:
                                                messages += _get_snapshot_info(y)
                    else:
                        messages = f"虚拟机{vm_name}未找到快照"          
                    return messages
            return f"未找到名为'{vm_name}'的虚拟机"
        except Exception as e:
            return f"获取虚拟机快照信息时出错：{str(e)}"
        finally:
            if container:
                container.Destroy()

class controls_info(object):
    #关闭vsphere主机
    def power_off_host(si,host_name):
        """ 关闭指定的vsphere主机 """
        content = si.RetrieveContent()
        # 使用 content.searchIndex 执行查找
        search_index = content.searchIndex
        host = search_index.FindByDnsName(dnsName=host_name, vmSearch=False)
        if host.name:
            # 检查主机当前状态
            if host.runtime.powerState == "poweredOn":
                try:
                    # 关闭vsphere主机
                    task = host.ShutdownHost_Task(force=True)
                    # 等待操作完成
                    WaitForTasks(si, [task])
                    message = 'vsphere主机:'+ host_name +' 正在关机'
                except Exception as e:
                    message = 'vsphere主机:'+ host_name +' 关机失败，错误：'+ e
        return message

    # 虚拟机开机
    def power_on_vm(si,vm_name):
        """ 对指定的虚拟机开机 """
        # 从已建立的连接中获取内容
        content = si.RetrieveContent()
        # 查找虚拟机
        vm = None
        container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        vms = container.view
        for v in vms:
            if v.name == vm_name:
                vm = v
                break
        if vm:
            # 检查虚拟机当前状态
            if vm.runtime.powerState == "poweredOff":
            # if vm.runtime.powerState == "poweredOn":
                # 开机虚拟机
                task = vm.PowerOnVM_Task()
                # task = vm.PowerOffVM_Task()
                # 等待操作完成
                WaitForTasks(si, [task])
                return f"虚拟机 '{vm_name}' 正在开机"
            else:
                return f"虚拟机 '{vm_name}' 已处于开机状态"
        else:
            return f"找不到虚拟机 '{vm_name}'"

    # 虚拟机关机
    def power_off_vm(si,vm_name):
        """ 对指定的虚拟机关机 """
        # 从已建立的连接中获取内容
        content = si.RetrieveContent()
        
        # 查找虚拟机
        vm = None
        container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        vms = container.view
        for v in vms:
            if v.name == vm_name:
                vm = v
                break
        if vm:
            # 检查虚拟机当前状态
            if vm.runtime.powerState == "poweredOn":
                # 关机虚拟机
                task = vm.PowerOffVM_Task()
                # 等待操作完成
                WaitForTasks(si, [task])
                return f"虚拟机 '{vm_name}' 正在关机"
            else:
                return f"虚拟机 '{vm_name}' 已处于关机状态"
        else:
            return f"找不到虚拟机 '{vm_name}'"
    
    # 虚拟机删除
    def delete_vms(si, vm_name):
        """ 删除指定的虚拟机 """
        content = si.RetrieveContent()
        container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        vms = container.view
        for vm in vms:
            if vm.name == vm_name:
                try:
                    if vm.runtime.powerState == "poweredOn":
                        # 如果虚拟机正在运行，首先关闭它
                        task = vm.PowerOff()
                        task_info = task.info
                        task_info.state = vim.TaskInfo.State.success
                        task_info.result = None
                        # print(f"等待虚拟机 {vm_name} 关机...")
                        WaitForTasks(si, [task])
                    
                    # 删除虚拟机
                    task = vm.Destroy()
                    task_info = task.info
                    task_info.state = vim.TaskInfo.State.success
                    task_info.result = None

                    start_time = time.time()
                    while task_info.state != vim.TaskInfo.State.success:
                        if time.time() - start_time > 300:  # 设置超时时间，单位秒
                            # raise Exception(f"删除虚拟机 {vm_name} 超时")
                            print({'code': 404, 'message': '虚拟机 %s 已超时5分钟' %vm_name})
                        time.sleep(5)  # 每5秒检查一次任务状态
                        task_info = task.info
                    print({'code': 200, 'message': '虚拟机 %s 已成功删除' %vm_name})
                except Exception as e:
                    print({'code': 404, 'message': ' %s' %e}) 

    #虚拟机创建快照
    def snapshot_vm(si, vm_name):
        """ 创建指定虚拟机的快照 """
        snapshot_name = f'快照 {time.strftime("%Y-%m-%d %H:%M:%S")}'
        description = f'{snapshot_name} 创建时间：{time.strftime("%Y-%m-%d %H:%M:%S")}\n创建人:管理软件创建'
        
        content = si.RetrieveContent()
        container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        vms = container.view
        
        try:
            vm = next((v for v in vms if v.name == vm_name), None)
            if vm:
                task = vm.CreateSnapshot_Task(name=snapshot_name, description=description, memory=True, quiesce=False)
                WaitForTasks(si, [task])
                return f"虚拟机'{vm_name}'创建快照，快照名：{snapshot_name}"
            else:
                return f"找不到名为'{vm_name}'的虚拟机"
        except Exception as e:
            return f"创建快照时出错：{str(e)}"
        finally:
            if container:
                container.Destroy()

class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VMware vCenter Login")
        self.geometry('300x150')
        self.iconbitmap('LockedIcon.ico')

        tk.Label(self).grid(row=0,column=0)
        tk.Label(self, text="Host Name:",width=15, anchor='e').grid(row=1,column=0,sticky='e')
        self.entry_host = tk.Entry(self, width=22)
        self.entry_host.grid(row=1,column=1)

        tk.Label(self, text="User Name:",width=15, anchor='e').grid(row=2,column=0,sticky='e')
        self.entry_user_name = tk.Entry(self, width=22)
        self.entry_user_name.grid(row=2,column=1)

        tk.Label(self, text="Password:",width=15, anchor='e').grid(row=3,column=0,sticky='e')
        self.entry_user_passwd = tk.Entry(self, show='*', width=22)
        self.entry_user_passwd.grid(row=3,column=1) 

        # 按钮 - 开始
        tk.Button(self, text="登 录", command=self.login,width=10).grid(column=0,row=4,padx=5, pady=15,sticky='e')
        # 按钮 - 取消
        tk.Button(self, text="退 出", command=self.quit,width=10).grid(column=1,row=4,padx=5, pady=15)

    def login(self):
        host = self.entry_host.get()
        user = self.entry_user_name.get()
        password = self.entry_user_passwd.get()
        si = connect_vsphere(host,user, password,'443')
        if si == None:
            if tk.messagebox.askretrycancel('重试', '账号或密码不正确，是否重试?') == True:
                self.mainloop()
            else:
                self.destroy() 
        else:
            self.destroy()
            MainWindow(host,user,password)  
            tk.messagebox.showinfo('提示', '登录成功！')

    def quit(self):
        result = messagebox.askyesno("确认退出", "您确定要退出吗？")
        if result:
            self.destroy() 
    
class MainWindow(tk.Tk):
    def __init__(self,hostname,username, password):
        super().__init__()
        self.title("VMware vCenter Server Manage")
        self.iconbitmap('download.ico')
        si = connect_vsphere(hostname,username, password,'443')
        self.top_container = tk.LabelFrame(self, text='VMware vCenter Info', font=('宋体', 12, 'bold'))
        self.top_container.grid(row=0,column=0)
        tk.Label(self.top_container, text=" ").grid(row=0,column=0)
        self.left_container = tk.LabelFrame(self.top_container, text='功 能 选 择：', font=('宋体', 10, 'bold'))
        self.left_container.grid(row=1,columnspan=2,column=0,sticky='ew')
        
        self.button_host_info = tk.Button(self.left_container, text="获取主机信息", width=15, command=lambda:self.get_vm_host_info(si))
        self.button_host_info.grid(row=1,column=0, padx=3, pady=5) 

        self.button_VM_info = tk.Button(self.left_container, text="获取VM信息", width=15, command=lambda:self.vm_info(si))
        self.button_VM_info.grid(row=1,column=1, padx=3, pady=5) 

        self.button_shutdown_host = tk.Button(self.left_container, text="关闭所有主机", width=15, command=lambda:self.shutdown_all_host(si))
        self.button_shutdown_host.grid(row=2,column=0, padx=3, pady=5) 
        #self.button_shutdown_host.configure(state='disabled')

        self.button_shutdown_vm = tk.Button(self.left_container, text="关闭所有VM", width=15, command=lambda:self.shutdown_all_vm(si))
        self.button_shutdown_vm.grid(row=2,column=1, padx=3, pady=5) 
        #self.button_shutdown_vm.configure(state='disabled')

        self.intvar_host = tk.LabelFrame(self.left_container)
        self.intvar_host.grid(row=3,column=0,rowspan=2)
        self.selected_hosts = []
        for index,host in enumerate(get_info.get_host_name(si)):
            var_name = 'intvar_host{}'.format(index+1)
            setattr(self, var_name, tk.IntVar())  # 创建变量 intvar_host1, intvar_host2, ...
            check_button = tk.Checkbutton(self.intvar_host, text=host['hostname'], variable=getattr(self, var_name), width=12)
            check_button.pack()
            check_button.config(command=lambda v=getattr(self, var_name), h=host['hostname']: self.update_selected_hosts(v.get(), h)) # 将每个多选框的状态与一个回调函数关联
        self.button_shutdown_host = tk.Button(self.left_container, text="关闭选择主机", width=12, command=lambda:self.shutdown_host(self.selected_hosts,si))
        self.button_shutdown_host.grid(row=3,column=1, padx=3, pady=5)
        self.button_get_host_info = tk.Button(self.left_container, text="主机详细信息", width=12, command=lambda:self.get_host_detail_info(self.selected_hosts,si))
        self.button_get_host_info.grid(row=4,column=1, padx=3, pady=5)
        tk.Label(self.top_container, text=" ").grid(row=2,column=0)
        self.vm_container = tk.LabelFrame(self.top_container, text='VM 管 理', font=('宋体', 10, 'bold'))
        self.vm_container.grid(row=3,columnspan=3,sticky='ew')
        tk.Label(self.vm_container, text="VM Name:").grid(row=0,column=0)
        self.entry_vm_contor = tk.Entry(self.vm_container)
        self.entry_vm_contor.grid(row=0,column=1)
        tk.Button(self.vm_container, text="查询VM信息", command=lambda:self.get_vm_info(si),width=11).grid(row=1,column=0,padx=5, pady=5)
        tk.Button(self.vm_container, text="查询VM快照", command=lambda:self.get_vm_snapshot_info(si),width=11).grid(row=1,column=1,padx=5, pady=5)
        tk.Button(self.vm_container, text="创建VM快照", command=lambda:self.snapshot_vm(si),width=11).grid(row=2,column=0,padx=5, pady=5)
        tk.Button(self.vm_container, text="VM开机", command=lambda:self.poweron_vm(si),width=11).grid(row=2,column=1,padx=5, pady=5)
        tk.Button(self.vm_container, text="VM关机", command=lambda:self.shutdown_vm(si),width=11).grid(row=3,column=0,padx=5, pady=5)
        tk.Button(self.vm_container, text="删除VM", command=lambda:self.delete_vm(si),width=11).grid(row=3,column=1,padx=5, pady=5)
        
        tk.Button(self.top_container, text="退出", command=self.page_quit,width=11).grid(row=5,column=1,padx=5, pady=10)
        tk.Button(self.top_container, text="清空", command=self.clear_text,width=11).grid(row=5,column=0,padx=5, pady=10)

        # 创建右侧时间
        self.time_row = tk.Label(self,text='')
        self.time_row.grid(row=3,columnspan=3,sticky="e")
        # 创建右侧文本框
        self.text_info = tk.LabelFrame(self, text='Return information', font=('宋体', 8))
        self.text_info.grid(row=0,column=1)

        self.text_box = tk.Text(self.text_info, height=36, width=150,)
        self.text_box.grid(row=0,column=0)
        self.text_box.tag_configure('left',justify='left')
        self.text_box.tag_add('left','1.0','end')

        self.get_current_time()

    def update_selected_hosts(self, state, hostname):
        """ 多选框选中的列表 """
        if state == 1:
            self.selected_hosts.append(hostname)
        else:
            self.selected_hosts.remove(hostname)

    def shutdown_host(self, selected_hosts,si):
        """ 关闭选中的vsphere 主机 """
        if len(selected_hosts) >= 1 :
            for host in selected_hosts:
                message = controls_info.power_off_host(si,host) +'\n  \n'
                self.text_box.insert(tk.END, message)
                tk.messagebox.showwarning("警告", message)
        else:
            tk.messagebox.showerror('错误', '未选中主机')

    def get_vm_host_info(self,si):
        """ 获取vsphere主机电源状态 """
        messages = ''
        for host in get_info.get_host_name(si):
            message  = '主机名：%s  电源状态：%s  \n' %(host['hostname'],host['powerstate'])
            messages+=message
        hostinfo = self.text_box.insert(tk.END, messages)
        return hostinfo
    def get_host_detail_info(self,selected_hosts,si):
        """ 获取vsphere 主机的详细信息 """
        if len(selected_hosts) >= 1 :
            for host in selected_hosts:
                info = get_info.get_host_template(si,host)
                message=''
                if info['status'] == '开机' :
                    message = """主机：%s %s %s 型号：%s CPU:%s,%s核,%s颗;内存：%s,已用%s剩余%s;硬盘：%s,已用%s剩余%s;虚拟机：%s \n  \n"""%(info['name'],info['status'],info['物理机总运行时长'],info['hardware_model'],info['cpu_model'].replace("  ", ""),info['cpu_cores'],info['cpu_sockets'],info['物理机总内存'],info['物理机内存使用情况'],info['mem_available'],info['物理机总存储空间大小'],info['物理机存储已用大小'],info['storage_available'],info['VM'])
                else:
                    message = """主机：%s %s \n  \n"""%(info['name'],info['status'])
                self.text_box.insert(tk.END, message)
        else:
            tk.messagebox.showerror('错误', '未选中主机')
    def get_vm_snapshot_info(self,si):
        """ 获取虚拟主机的快照信息 """
        messages = ''
        host = str(self.entry_vm_contor.get()).replace("'",'').replace(' ','') #host单个名称，校验多个查询
        if host != '':
            # 检查是否字符串中包含分号
            if ';' in host:
                host = host.split(';')
            # 检查是否字符串中包含逗号
            elif ',' in host:
                host = host.split(',')
            else:
                host = [host]
            for i in host:
                vmhost = [vm['vmname'] for vm in get_info.get_vm_template(si)]
                if i in vmhost:
                    # 获取虚拟机详情
                    message = i + '\n' + str(get_info.get_vm_snapshot(si, i)) +' \n  \n'
                    messages += message
                else:
                    message = i + '\n 未找到该主机: {}\n  \n'.format(i)
                    messages += message
            # 将消息插入到文本框
            self.text_box.insert(tk.END, messages)
        else:
            message = '输入的虚拟机名为空！请重新输入 \n  \n'
            self.text_box.insert(tk.END, message)

    def vm_info(self,si):
        """ 获取所有虚拟机的的详细信息 """
        messages = ''
        for vm in get_info.get_vm_template(si):
            message  = '虚拟机名：%-20s 电源状态：%-10s 内存：%-8s IP地址:%-15s 宿主机：%-15s 系统：%s \n' %(vm['vmname'],vm['status'],vm['mem'],vm['ip'],vm['vspherehost'],vm['system'])
            messages+=message
        vminfo = self.text_box.insert(tk.END, messages)
        return vminfo
    def get_vm_info(self,si):
        """ 获取选中的虚拟机信息 """
        messages = ''
        host = str(self.entry_vm_contor.get()).replace("'",'').replace(' ','') #host单个名称，校验多个查询
        if host != '':
            # 检查是否字符串中包含分号
            if ';' in host:
                host = host.split(';')
            # 检查是否字符串中包含逗号
            elif ',' in host:
                host = host.split(',')
            else:
                host = [host]
            for i in host:
                vmhost = [vm['vmname'] for vm in get_info.get_vm_template(si)]
                if i in vmhost:
                    # 获取虚拟机详情
                    message = i + '\n' + str(get_info.get_vm_details(si, i)) +' \n  \n'
                    messages += message
                else:
                    message = i + '\n 未找到该主机: {}\n  \n'.format(i)
                    messages += message
            # 将消息插入到文本框
            self.text_box.insert(tk.END, messages)
        else:
            message = '输入的虚拟机名为空！请重新输入 \n  \n'
            self.text_box.insert(tk.END, message)
        #return message
    def poweron_vm(self,si):
        """ 开机-选中的虚拟机 """
        messages = ''
        host = str(self.entry_vm_contor.get()).replace("'",'').replace(' ','') #host单个名称，校验多个查询
        
        if host != '':
            # 检查是否字符串中包含分号
            if ';' in host:
                host = host.split(';')
            # 检查是否字符串中包含逗号
            elif ',' in host:
                host = host.split(',')
            else:
                host = [host]
            for i in host:
                vmhost = [vm['vmname'] for vm in get_info.get_vm_template(si)]
                if i in vmhost:
                    # 获取虚拟机详情
                    message = i + '\n' + str(controls_info.power_on_vm(si, i)) +' \n  \n'
                    messages += message
                else:
                    message = i + '\n 未找到该主机: {}\n  \n'.format(i)
                    messages += message
            # 将消息插入到文本框
            self.text_box.insert(tk.END, messages)
        else:
            message = '输入的虚拟机名为空！请重新输入 \n  \n'
            self.text_box.insert(tk.END, message)
    def shutdown_vm(self,si):
        """ 关机-选择的虚拟机 """
        messages = ''
        host = str(self.entry_vm_contor.get()).replace("'",'').replace(' ','') #host单个名称，校验多个查询
        
        if host != '':
            # 检查是否字符串中包含分号
            if ';' in host:
                host = host.split(';')
            # 检查是否字符串中包含逗号
            elif ',' in host:
                host = host.split(',')
            else:
                host = [host]
            for i in host:
                vmhost = [vm['vmname'] for vm in get_info.get_vm_template(si)]
                if i in vmhost:
                    # 获取虚拟机详情
                    message = i + '\n' + str(controls_info.power_off_vm(si, i)) +' \n  \n'
                    messages += message
                else:
                    message = i + '\n 未找到该主机: {}\n  \n'.format(i)
                    messages += message
            # 将消息插入到文本框
            self.text_box.insert(tk.END, messages)
        else:
            message = '输入的虚拟机名为空！请重新输入 \n  \n'
            self.text_box.insert(tk.END, message)
    def delete_vm(self,si):
        """ 删除-选中的虚拟机 """
        messages = ''
        host = str(self.entry_vm_contor.get()).replace("'",'').replace(' ','') #host单个名称，校验多个查询
        
        if host != '':
            # 检查是否字符串中包含分号
            if ';' in host:
                host = host.split(';')
            # 检查是否字符串中包含逗号
            elif ',' in host:
                host = host.split(',')
            else:
                host = [host]
            for i in host:
                vmhost = [vm['vmname'] for vm in get_info.get_vm_template(si)]
                if i in vmhost:
                    # 获取虚拟机详情
                    message = i + '\n' + str(controls_info.delete_vms(si, i)) +' \n  \n'
                    messages += message
                else:
                    message = i + '\n 未找到该主机: {}\n  \n'.format(i)
                    messages += message
            # 将消息插入到文本框
            self.text_box.insert(tk.END, messages)
        else:
            message = '输入的虚拟机名为空！请重新输入 \n  \n'
            self.text_box.insert(tk.END, message)
    def snapshot_vm(self,si):
        """ 获取选中虚拟机快照信息 """
        messages = ''
        host = str(self.entry_vm_contor.get()).replace("'",'').replace(' ','') #host单个名称，校验多个查询
        
        if host != '':
            # 检查是否字符串中包含分号
            if ';' in host:
                host = host.split(';')
            # 检查是否字符串中包含逗号
            elif ',' in host:
                host = host.split(',')
            else:
                host = [host]
            for i in host:
                vmhost = [vm['vmname'] for vm in get_info.get_vm_template(si)]
                if i in vmhost:
                    # 获取虚拟机详情
                    message = i + '\n' + str(controls_info.snapshot_vm(si, i)) +' \n  \n'
                    messages += message
                else:
                    message = i + '\n 未找到该主机: {}\n  \n'.format(i)
                    messages += message
            # 将消息插入到文本框
            self.text_box.insert(tk.END, messages)
        else:
            message = '输入的虚拟机名为空！请重新输入 \n  \n'
            self.text_box.insert(tk.END, message)

    def shutdown_all_vm(self,si):
        """ 关闭所有的虚拟机 """
        messages = ''
        for vm in get_info.get_vm_template(si):
            if vm['status'] == 'poweredOn':
                controls_info.power_off_vm(si,vm['vmname'])
            message = '正在关闭vsphere主机:'+ vm['vmname']+'\n'
            messages+=message
        shutdowninfo = self.text_box.insert(tk.END, messages)
        return shutdowninfo
    def shutdown_all_host(self,si):
        """ 关闭所有vsphere主机 """
        messages = ''
        for host in get_info.get_host_name(si):
            if host['powerstate'] == 'poweredOn':
                controls_info.power_off_host(si,host['hostname'])
            message = '正在关闭vsphere主机:'+ host['hostname'] +'\n  \n'
            messages+=message
        shutdowninfo = self.text_box.insert(tk.END, messages)
        return shutdowninfo

    def get_current_time(self):
        """
        自动刷新显示时间
        """
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.time_row.config(text=current_time)
        self.after(1000, self.get_current_time)
    def clear_text(self):
        """ 清理文本框内容 """
        self.text_box.delete('1.0',tk.END)
    def page_quit(self):
        """ 退出当前应用 """
        result = messagebox.askyesno("确认退出", "您确定要退出吗？")
        if result:
            self.destroy()
    
if __name__ == "__main__":
    login_window = LoginWindow()
    login_window.mainloop()
