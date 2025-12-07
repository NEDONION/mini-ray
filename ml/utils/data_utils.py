# ml/data_utils.py
import os
from torchvision.datasets import CIFAR10
from torchvision import transforms

def ensure_cifar10_downloaded(global_root="/data", project_root="./data"):
    if os.path.exists(os.path.join(global_root, "cifar-10-batches-py")):
        print(f"✔ CIFAR-10 已存在于全局目录: {global_root}")
        return global_root

    if os.path.exists(os.path.join(project_root, "cifar-10-batches-py")):
        print(f"✔ CIFAR-10 已存在于项目目录: {project_root}")
        return project_root

    print("📥 CIFAR-10 不存在，正在下载到项目目录 ./data ...")
    os.makedirs(project_root, exist_ok=True)
    CIFAR10(root=project_root, train=True, download=True, transform=transforms.ToTensor())
    print("✅ CIFAR-10 下载完成")
    return project_root
