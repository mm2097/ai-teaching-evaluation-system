"""题目课程分类器。

按关键词匹配将题目归类到：1=计算机网络 / 2=操作系统 / 3=数据结构 / None=跳过（组成原理或无法判断）。
使用评分制：各课程关键词命中数打分，取最高分；若所有课程得分均为 0 则跳过。
"""

from __future__ import annotations

# 课程关键词表（任一命中即加分）
COURSE_KEYWORDS: dict[int, dict] = {
    1: {
        "name": "计算机网络",
        "keywords": [
            "IP", "TCP", "UDP", "HTTP", "HTTPS", "路由", "以太网", "ARP",
            "OSI", "子网", "掩码", "拥塞", "握手", "滑动窗口", "DNS", "DHCP",
            "端口", "数据报", "分组", "协议栈", "网桥", "交换机", "路由器",
            "MAC地址", "MAC 地址", "CSMA", "令牌", "帧", "信道", "带宽", "波特",
            "NAT", "ICMP", "BGP", "OSPF", "RIP", "FTP", "SMTP", "POP3",
            "IMAP", "TCP/IP", "网络层", "传输层", "应用层", "数据链路层",
            "物理层", "会话层", "表示层", "三次握手", "四次挥手", "可靠传输",
            "流量控制", "IP地址", "IP 地址", "子网划分", "CIDR", "VLSM",
            "曼彻斯特", "编码", "香农", "奈奎斯特", "电路交换", "报文交换",
            "分组交换", "虚电路", "套接字", "socket", "Socket", "MSS", "MTU",
            "RTT", "往返时间", "超时", "重传", "确认", "ACK",
        ],
    },
    2: {
        "name": "操作系统",
        "keywords": [
            "进程", "线程", "死锁", "页面置换", "虚拟内存", "调度算法",
            "磁盘调度", "中断", "并发", "互斥", "信号量", "PV操作", "PV操作",
            "管程", "文件系统", "分页", "分段", "段页式", "抖动", "颠簸",
            "上下文切换", "临界区", "同步互斥", "异步", "DMA", "SPOOLing",
            "假脱机", "FCFS", "SJF", "优先级调度", "时间片轮转", "多级反馈",
            "LRU", "FIFO", "OPT", "CLOCK", "缺页", "缺页中断", "TLB",
            "快表", "inode", "索引节点", "FAT", "NTFS", "EXT", "目录",
            "管道", "消息队列", "共享存储", "共享内存", "信号",
            "读者写者", "生产者消费者", "哲学家进餐", "银行家算法",
            "安全序列", "资源分配", "作业", "地址翻译", "地址变换",
            "逻辑地址", "物理地址", "页表", "多级页表", "反向页表",
            "写时复制", "Copy-on-Write", "程序计数器", "PCB",
            "就绪态", "阻塞态", "运行态", "挂起", "唤醒",
            "I/O控制", "I/O 控制", "设备驱动", "缓冲区", "高速缓存",
        ],
    },
    3: {
        "name": "数据结构",
        "keywords": [
            "二叉树", "链表", "栈", "队列", "树", "图", "排序",
            "哈希表", "Hash", "哈希", "散列", "递归", "查找", "堆",
            "遍历", "森林", "邻接", "邻接矩阵", "邻接表", "BST",
            "AVL树", "AVL", "红黑树", "B树", "B+树", "B-树",
            "快速排序", "归并排序", "冒泡排序", "插入排序", "选择排序",
            "希尔排序", "堆排序", "基数排序", "计数排序", "桶排序",
            "时间复杂度", "空间复杂度", "渐进", "大O表示",
            "数组", "矩阵", "串", "模式匹配", "前缀", "后缀",
            "中缀", "表达式", "前序遍历", "中序遍历", "后序遍历",
            "层序遍历", "完全二叉树", "满二叉树", "Huffman",
            "霍夫曼树", "哈夫曼树", "最优二叉树", "带权路径长度",
            "最短路径", "Dijkstra", "迪杰斯特拉", "Floyd", "弗洛伊德",
            "Bellman-Ford", "最小生成树", "Prim", "Kruskal",
            "拓扑排序", "关键路径", "AOV网", "AOE网", "AOV", "AOE",
            "DAG", "有向无环图", "连通图", "强连通", "生成树",
            "KMP", "next数组", "next 数组", "失败指针",
            "平衡二叉树", "线索二叉树", "并查集", "跳表", "跳表",
            "十字链表", "三元组", "十字链表", "多重表",
        ],
    },
}

# 组成原理关键词（命中即跳过，不进课程库）
SKIP_KEYWORDS: list[str] = [
    "寄存器", "ALU", "运算器", "浮点", "浮点数", "流水线",
    "总线", "总线仲裁", "寻址方式", "寻址模式", "指令系统",
    "微程序", "微指令", "硬布线", "存储器扩展", "存储芯片",
    "ROM", "RAM", "EPROM", "EEPROM", "Cache行", "Cache 行",
    "直接映射", "全相联", "组相联", "写回", "全写法", "写直达",
    "中断系统", "I/O接口", "I/O 接口", "补码", "原码", "反码", "移码",
    "指令流水", "数据相关", "控制相关", "结构相关", "数据冒险",
    "控制冒险", "结构冒险", "分支预测", "乱序执行",
    "IEEE754", "IEEE 754", "阶码", "尾数", "对阶",
]


def classify(text: str) -> tuple[int | None, str]:
    """将题目文本分类到课程。

    参数：
        text: 题干 + 知识点 + 选项（拼在一起，信息越多分类越准）

    返回：
        (course_id, reason)
        - course_id: 1/2/3 或 None（跳过）
        - reason: 分类原因说明
    """
    if not text or not text.strip():
        return None, "文本为空"

    # 先检查组成原理关键词（优先级最高，因为 408 中组成原理题不进库）
    for kw in SKIP_KEYWORDS:
        if kw in text:
            return None, f"命中组成原理关键词「{kw}」，跳过"

    # 各课程打分
    scores: dict[int, int] = {}
    matched: dict[int, list[str]] = {}
    for cid, info in COURSE_KEYWORDS.items():
        hits = [kw for kw in info["keywords"] if kw in text]
        scores[cid] = len(hits)
        matched[cid] = hits

    best_cid = max(scores, key=scores.get) if scores else None
    best_score = scores.get(best_cid, 0)

    if best_score == 0:
        return None, "无关键词命中，无法判断课程"

    # 检查是否有并列最高
    top_courses = [cid for cid, s in scores.items() if s == best_score]
    if len(top_courses) > 1:
        names = [COURSE_KEYWORDS[c]["name"] for c in top_courses]
        return None, f"多课程并列命中（{names}），跳过避免误分"

    return best_cid, f"命中{COURSE_KEYWORDS[best_cid]['name']}关键词：{matched[best_cid][:3]}"


def course_name(course_id: int | None) -> str:
    """获取课程名称。"""
    if course_id is None:
        return "跳过"
    return COURSE_KEYWORDS.get(course_id, {}).get("name", "未知")
