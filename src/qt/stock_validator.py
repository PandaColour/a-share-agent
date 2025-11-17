# -*- coding: utf-8 -*-
"""
股票代码校验工具
用于验证和补全股票代码
"""
import re
from typing import Optional, Tuple, List
import akshare as ak
from PyQt6.QtCore import QObject, pyqtSignal


class StockValidator(QObject):
    """股票代码验证器"""

    # 信号：校验结果(成功, 消息, 完整代码, 股票名称)
    validation_result = pyqtSignal(bool, str, str, str)

    def __init__(self):
        super().__init__()
        # 股票代码映射缓存
        self.stock_cache = {}

    def validate_stock_code(self, input_text: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        验证股票代码并获取完整信息

        Args:
            input_text: 用户输入的股票代码或名称

        Returns:
            Tuple[是否有效, 消息, 完整代码, 股票名称]
        """
        if not input_text or not input_text.strip():
            return False, "请输入股票代码或名称", None, None

        input_text = input_text.strip()

        # 1. 如果是6位数字，可能是股票代码
        if re.match(r'^\d{6}$', input_text):
            return self._validate_6digit_code(input_text)

        # 2. 如果已经是完整格式（如000001.SZ）
        elif re.match(r'^\d{6}\.[A-Z]{2}$', input_text):
            return self._validate_full_code(input_text)

        # 3. 如果是股票名称，进行搜索
        elif re.match(r'^[\u4e00-\u9fa5]+$', input_text):
            return self._validate_stock_name(input_text)

        else:
            return False, "输入格式不正确，请输入6位数字代码或股票名称", None, None

    def _validate_6digit_code(self, code: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """验证6位数字代码"""
        try:
            # 根据代码前缀判断交易所
            if code.startswith(('00', '30')):
                # 深圳
                full_code = f"{code}.SZ"
            elif code.startswith(('60', '68')):
                # 上海
                full_code = f"{code}.SH"
            elif code.startswith(('8', '4')):
                # 北京
                full_code = f"{code}.BJ"
            else:
                return False, f"不支持的股票代码前缀: {code[:2]}", None, None

            # 尝试获取股票信息进行验证
            stock_info = self._get_stock_info(full_code)
            if stock_info:
                name = stock_info.get('name', '')
                return True, f"找到股票: {name} ({full_code})", full_code, name
            else:
                return False, f"未找到股票代码: {full_code}", None, None

        except Exception as e:
            return False, f"验证股票代码时出错: {str(e)}", None, None

    def _validate_full_code(self, full_code: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """验证完整格式的股票代码"""
        try:
            stock_info = self._get_stock_info(full_code)
            if stock_info:
                name = stock_info.get('name', '')
                return True, f"股票代码有效: {name} ({full_code})", full_code, name
            else:
                return False, f"未找到股票代码: {full_code}", None, None
        except Exception as e:
            return False, f"验证股票代码时出错: {str(e)}", None, None

    def _validate_stock_name(self, name: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """通过股票名称查找代码"""
        try:
            # 使用AkShare搜索股票
            stock_list = ak.stock_info_a_code_name()

            # 搜索匹配的股票
            matches = stock_list[stock_list['name'].str.contains(name, na=False)]

            if len(matches) == 0:
                return False, f"未找到股票名称包含: {name}", None, None
            elif len(matches) == 1:
                # 精确匹配
                row = matches.iloc[0]
                code = row['code']
                stock_name = row['name']

                # 补全交易所后缀
                if code.startswith(('00', '30')):
                    full_code = f"{code}.SZ"
                elif code.startswith(('60', '68')):
                    full_code = f"{code}.SH"
                elif code.startswith(('8', '4')):
                    full_code = f"{code}.BJ"
                else:
                    full_code = code

                return True, f"找到股票: {stock_name} ({full_code})", full_code, stock_name
            else:
                # 多个匹配，返回第一个
                row = matches.iloc[0]
                code = row['code']
                stock_name = row['name']

                if code.startswith(('00', '30')):
                    full_code = f"{code}.SZ"
                elif code.startswith(('60', '68')):
                    full_code = f"{code}.SH"
                elif code.startswith(('8', '4')):
                    full_code = f"{code}.BJ"
                else:
                    full_code = code

                return True, f"找到多个匹配，选择: {stock_name} ({full_code})", full_code, stock_name

        except Exception as e:
            return False, f"搜索股票名称时出错: {str(e)}", None, None

    def _get_stock_info(self, code: str) -> Optional[dict]:
        """获取股票基本信息"""
        try:
            # 先检查缓存
            if code in self.stock_cache:
                return self.stock_cache[code]

            # 获取实时行情数据进行验证
            if code.endswith('.SZ'):
                symbol = code[:-3]
                data = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date="20241101", end_date="20241110", adjust="")
            elif code.endswith('.SH'):
                symbol = code[:-3]
                data = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date="20241101", end_date="20241110", adjust="")
            elif code.endswith('.BJ'):
                symbol = code[:-3]
                data = ak.stock_bj_hist(symbol=symbol, period="daily", start_date="20241101", end_date="20241110", adjust="")
            else:
                return None

            if data is not None and len(data) > 0:
                # 获取股票名称
                stock_list = ak.stock_info_a_code_name()
                stock_info = stock_list[stock_list['code'] == code[:-3]]

                if len(stock_info) > 0:
                    name = stock_info.iloc[0]['name']
                    result = {'code': code, 'name': name, 'valid': True}
                    self.stock_cache[code] = result
                    return result

            return None

        except Exception as e:
            print(f"获取股票信息失败 {code}: {e}")
            return None

    def validate_stock_code_async(self, input_text: str):
        """异步验证股票代码"""
        # 这里可以使用线程，但对于简单操作，直接调用即可
        result = self.validate_stock_code(input_text)
        self.validation_result.emit(*result)