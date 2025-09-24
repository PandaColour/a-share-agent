# 安装指南

本文档提供详细的依赖安装指导，特别是AI因子系统的相关依赖。

## 🚀 快速安装

### 基础安装
```bash
# 安装基础依赖
pip install -r requirements.txt
```

## 🔧 特殊依赖安装指南

### 1. TA-Lib 技术分析库

TA-Lib是AI因子系统的核心依赖，但安装可能比较复杂：

#### Windows 安装
```bash
# 方法1：使用预编译包（推荐）
pip install TA-Lib

# 方法2：如果方法1失败，从whl文件安装
# 访问 https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
# 下载对应Python版本的whl文件，然后：
pip install TA_Lib-0.4.24-cp39-cp39-win_amd64.whl  # 示例文件名
```

#### macOS 安装
```bash
# 先安装brew（如果没有）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装ta-lib库
brew install ta-lib

# 安装Python包
pip install TA-Lib
```

#### Linux 安装
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install build-essential wget
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install

# 安装Python包
pip install TA-Lib
```

### 2. CVXPY 凸优化库

```bash
# 基础安装
pip install cvxpy

# 如果需要更多求解器（可选）
pip install cvxpy[CBC]
pip install cvxpy[GLPK]
```

### 3. 机器学习库

```bash
# scikit-learn
pip install scikit-learn

# 图表库
pip install matplotlib seaborn
```

## 🐍 Python版本要求

- **Python 3.8+** （推荐3.9或3.10）
- 确保使用64位Python版本

## 🔍 安装验证

### 验证基础功能
```bash
python -c "import pandas, numpy, yfinance, requests; print('基础依赖安装成功')"
```

### 验证AI因子系统依赖
```bash
python -c "import talib, sklearn, cvxpy, matplotlib, seaborn; print('AI因子系统依赖安装成功')"
```

### 完整功能测试
```bash
# 测试AI因子系统（使用模拟数据，不依赖网络）
python test_auto_factor_system.py
```

## 🚨 常见问题解决

### 1. TA-Lib 安装失败

**错误**: `error: Microsoft Visual C++ 14.0 is required`

**解决**:
- Windows: 安装 Visual Studio Build Tools
- 或者使用预编译包: `pip install --only-binary=all TA-Lib`

### 2. CVXPY 安装失败

**错误**: `Failed building wheel for cvxpy`

**解决**:
```bash
# 先安装必要的编译工具
pip install --upgrade pip setuptools wheel
pip install cvxpy --no-cache-dir
```

### 3. 内存不足

**错误**: `MemoryError` 在安装过程中

**解决**:
```bash
# 分批安装
pip install pandas numpy scipy
pip install scikit-learn
pip install talib
pip install cvxpy matplotlib seaborn
```

## 🎯 最小化安装（仅基础功能）

如果你只想使用基础的股票分析功能（不包含AI因子），可以安装最小依赖：

```bash
# 创建最小依赖文件
cat > requirements_minimal.txt << EOF
pandas>=1.5.0
numpy>=1.24.0
yfinance>=0.2.0
requests>=2.28.0
akshare>=1.17.46
jieba>=0.42.1
scipy>=1.16.2
EOF

# 安装最小依赖
pip install -r requirements_minimal.txt
```

**注意**: 使用最小化安装时，AI因子系统将自动禁用，不影响基础分析功能。

## 🐋 Docker 安装（推荐）

为了避免依赖冲突，推荐使用Docker：

```dockerfile
FROM python:3.9-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 安装TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr \
    && make && make install \
    && cd .. && rm -rf ta-lib*

# 复制并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . /app
WORKDIR /app

CMD ["python", "main.py"]
```

## 📞 获取帮助

如果遇到安装问题，可以：

1. **检查Python版本**: `python --version`
2. **检查pip版本**: `pip --version` 
3. **更新pip**: `pip install --upgrade pip`
4. **清理pip缓存**: `pip cache purge`
5. **使用国内镜像**:
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

安装成功后，运行 `python main.py` 即可享受AI增强的股票分析系统！