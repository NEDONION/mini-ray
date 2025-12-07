import os
from torchvision.datasets import CIFAR10
from torchvision import transforms

def ensure_cifar10_downloaded():
    """
    自动寻找 CIFAR-10 数据集所在目录：
    1. /data
    2. /root/data
    3. ~/data
    4. ./data
    都找不到就下载到 ./data
    """
    possible_dirs = [
        "/data",
        "/root/data",
        os.path.expanduser("~/data"),
        "./data"
    ]

    for d in possible_dirs:
        path = os.path.join(d, "cifar-10-batches-py")
        if os.path.exists(path):
            print(f"✔ CIFAR-10 已存在: {d}")
            return d

    # 如果都不存在 → 下载到 ./data
    print("📥 CIFAR-10 不存在，正在下载到 ./data ...")
    d = "./data"
    os.makedirs(d, exist_ok=True)
    CIFAR10(root=d, train=True, download=True, transform=transforms.ToTensor())
    print("✅ CIFAR-10 下载完成")
    return d
