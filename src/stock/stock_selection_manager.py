# -*- coding: utf-8 -*-
"""
股票选择管理器
独立管理动态选股逻辑，支持缓存和每日执行一次
"""

import os
import json
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from .dynamic_stock_selector import DynamicStockSelector, get_dynamic_stock_list, get_dynamic_stock_list_with_stats

logger = logging.getLogger(__name__)

class StockSelectionManager:
    """股票选择管理器 - 管理固定股票和动态选股的整合"""

    def __init__(self, config_manager=None):
        """
        初始化股票选择管理器

        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.cache_file = self._get_cache_file_path()
        self.dynamic_selector = DynamicStockSelector(config_manager)

    def _get_cache_file_path(self) -> Path:
        """获取缓存文件路径"""
        # 获取项目根目录
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent
        cache_file = project_root / "config" / "dynamic_stock.json"

        # 确保config目录存在
        cache_file.parent.mkdir(exist_ok=True)

        return cache_file

    def _load_cached_data(self) -> Optional[Dict]:
        """
        加载缓存的选股数据

        Returns:
            缓存数据字典，如果文件不存在或格式错误返回None
        """
        try:
            if not self.cache_file.exists():
                logger.info("缓存文件不存在，需要重新选股")
                return None

            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 验证数据结构
            required_fields = ['date', 'stocks', 'metadata']
            if not all(field in data for field in required_fields):
                logger.warning("缓存文件格式不正确，需要重新选股")
                return None

            logger.info(f"成功加载缓存数据，选股日期: {data['date']}")
            return data

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"读取缓存文件失败: {e}")
            return None

    def _enhance_stock_info(self, stocks: List[Tuple[str, str]]) -> List[Dict]:
        """
        增强股票信息，添加市场、行业等详细信息

        Args:
            stocks: (symbol, name) 格式的股票列表

        Returns:
            包含详细信息的股票字典列表
        """
        enhanced_stocks = []

        # 加载持仓股票配置获取已知信息
        const_config = self._load_hold_stock_config()
        all_known_stocks = {}

        # 建立已知股票的映射
        for stock in const_config.get('hold_stocks', []):
            all_known_stocks[stock['symbol']] = stock

        # 初始化数据源提供者（用于获取行业信息）
        data_provider = self._get_data_provider()

        for symbol, name in stocks:
            # 尝试从已知股票中获取信息
            known_info = all_known_stocks.get(symbol, {})

            # 推断市场信息
            market = "未知"
            if symbol.endswith('.SZ'):
                market = "深圳"
            elif symbol.endswith('.SH'):
                market = "上海"
            elif symbol.endswith('.BJ'):
                market = "北京"

            # 推断来源
            source = "config"  # 默认来源
            reason = known_info.get('reason', '动态选择')

            # 获取行业信息（新增）
            sector = known_info.get('sector', '未分类')
            if sector == '未分类':
                # 从数据源获取实时行业信息
                sector = self._get_stock_sector(symbol, data_provider)

            # 构建增强的股票信息
            enhanced_stock = {
                "symbol": symbol,
                "name": name,
                "market": known_info.get('market', market),
                "sector": sector,  # 使用增强后的行业信息
                "source": source,
                "reason": reason,
                "score": 70.0,  # 默认评分
                "price": 0.0,   # 需要实时获取
                "change_pct": 0.0,
                "market_cap": 0.0,
                "pe_ratio": 0.0,
                "selection_timestamp": datetime.now().isoformat()
            }

            enhanced_stocks.append(enhanced_stock)

        return enhanced_stocks

    def _get_data_provider(self):
        """
        获取数据源提供者实例（复用现有的多数据源架构）

        Returns:
            MultiSourceDataProvider实例，如果初始化失败返回None
        """
        try:
            from src.data.multi_source_data_provider import MultiSourceDataProvider

            # 如果有配置管理器，传递给数据提供者
            if self.config_manager:
                # 尝试从配置管理器获取统一配置文件路径
                config_file = None
                if hasattr(self.config_manager, 'config_file'):
                    config_file = self.config_manager.config_file
                return MultiSourceDataProvider(config_file=config_file)
            else:
                # 使用默认配置
                return MultiSourceDataProvider()

        except Exception as e:
            logger.error(f"初始化数据源提供者失败: {e}")
            return None

    def _get_stock_sector(self, symbol: str, data_provider) -> str:
        """
        从数据源获取股票行业信息（支持多数据源降级）

        Args:
            symbol: 股票代码
            data_provider: 数据源提供者实例

        Returns:
            行业信息字符串，获取失败返回'未分类'
        """
        if not data_provider:
            logger.debug(f"数据源提供者未初始化，无法获取 {symbol} 的行业信息")
            return '未分类'

        try:
            logger.debug(f"正在获取 {symbol} 的行业信息...")

            # 调用多数据源的 get_stock_info 方法
            stock_info = data_provider.get_stock_info(symbol)

            if not stock_info:
                logger.debug(f"未获取到 {symbol} 的基本信息")
                return '未分类'

            # 尝试多种可能的行业字段
            sector_fields = ['industry', 'sector', '行业', '所属行业', 'INDUSTRY']
            sector = '未分类'

            for field in sector_fields:
                if field in stock_info and stock_info[field]:
                    sector = str(stock_info[field]).strip()
                    if sector and sector != 'nan' and sector != 'None' and sector != '未分类':
                        logger.debug(f"✅ 从字段 '{field}' 获取到 {symbol} 的行业信息: {sector}")
                        break

            # 如果还是未分类，尝试根据股票名称推断
            if sector == '未分类':
                sector = self._infer_sector_from_name(symbol, stock_info.get('name', ''))

            return sector

        except Exception as e:
            logger.warning(f"获取 {symbol} 行业信息失败: {e}")
            return '未分类'

    def _infer_sector_from_name(self, symbol: str, name: str) -> str:
        """
        根据股票名称推断行业分类（备选方案）

        Args:
            symbol: 股票代码
            name: 股票名称

        Returns:
            推断的行业分类
        """
        if not name:
            return '未分类'

        try:
            # 定义行业关键词映射
            sector_keywords = {
                '银行': ['银行'],
                '保险': ['保险', '人寿', '财险'],
                '证券': ['证券', '券商', '投资'],
                '房地产': ['房地产', '地产', '置业', '开发'],
                '建筑建材': ['建筑', '建材', '建工', '水泥', '钢铁'],
                '医药生物': ['医药', '生物', '制药', '医疗', '健康'],
                '食品饮料': ['食品', '饮料', '酒业', '茅台', '五粮液', '乳业'],
                '汽车': ['汽车', '车辆', '客车'],
                '电子': ['电子', '科技', '信息', '通信', '半导体'],
                '计算机': ['软件', '网络', '计算机', '数据', '云'],
                '化工': ['化工', '化学', '石化'],
                '机械设备': ['机械', '设备', '制造'],
                '电力设备': ['电力', '电气', '能源'],
                '公用事业': ['水务', '燃气', '供电'],
                '传媒': ['传媒', '广告', '文化', '影视'],
                '交通运输': ['交通', '运输', '航空', '港口'],
                '商业贸易': ['商业', '贸易', '零售', '超市']
            }

            # 按优先级匹配
            for sector, keywords in sector_keywords.items():
                for keyword in keywords:
                    if keyword in name:
                        logger.debug(f"根据名称推断 {symbol}({name}) 行业为: {sector}")
                        return sector

            logger.debug(f"无法推断 {symbol}({name}) 的行业分类")
            return '未分类'

        except Exception as e:
            logger.debug(f"推断 {symbol} 行业分类失败: {e}")
            return '未分类'

    def _save_cached_data(self, stocks: List[Tuple[str, str]], metadata: Dict):
        """
        保存选股数据到缓存文件

        Args:
            stocks: 选中的股票列表
            metadata: 元数据信息
        """
        try:
            # 增强股票信息
            enhanced_stocks = self._enhance_stock_info(stocks)

            # 更新metadata中的缓存信息
            metadata_copy = metadata.copy()
            metadata_copy['cache_info'] = {
                'description': 'Dynamic stock selection cache file with enhanced stock information',
                'version': '2.0',
                'note': 'This file is automatically generated and updated daily. Contains detailed stock metadata for easy migration to hold_stock.json'
            }

            cache_data = {
                'date': str(date.today()),
                'timestamp': datetime.now().isoformat(),
                'stocks': enhanced_stocks,  # 使用增强的股票信息
                'metadata': metadata_copy
            }

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            logger.info(f"选股结果已保存到缓存: {len(enhanced_stocks)}只股票（包含详细信息）")

        except IOError as e:
            logger.error(f"保存缓存文件失败: {e}")

    def _is_cache_valid(self, cached_data: Dict) -> bool:
        """
        检查缓存是否有效（当日有效）

        Args:
            cached_data: 缓存数据

        Returns:
            True表示缓存有效，False表示需要重新选股
        """
        try:
            cached_date = cached_data.get('date')
            if not cached_date:
                return False

            # 比较日期
            today = str(date.today())
            is_valid = cached_date == today

            if is_valid:
                logger.info("缓存数据有效，使用今日已选股票")
            else:
                logger.info(f"缓存数据过期，缓存日期: {cached_date}, 今日: {today}")

            return is_valid

        except Exception as e:
            logger.error(f"检查缓存有效性失败: {e}")
            return False

    def _get_config_stocks(self) -> List[str]:
        """
        获取配置文件中的固定股票列表

        Returns:
            固定股票列表
        """
        try:
            if not self.config_manager:
                logger.warning("配置管理器未初始化，使用默认股票列表")
                return self._get_default_stocks()

            # 从配置中获取固定股票
            config_stocks = []

            # 尝试从unified_config.json获取
            if hasattr(self.config_manager, 'get'):
                # 获取配置的股票列表
                stock_selection_config = self.config_manager.get('stock_selection', {})
                if 'config_stocks' in stock_selection_config:
                    config_stocks = stock_selection_config['config_stocks']
                else:
                    # 从其他可能的配置位置获取
                    analysis_settings = self.config_manager.get('analysis_settings', {})
                    if 'target_stocks' in analysis_settings:
                        config_stocks = analysis_settings['target_stocks']

            # 如果配置为空，使用默认股票
            if not config_stocks:
                logger.warning("配置中未找到股票列表，使用默认股票")
                config_stocks = self._get_default_stocks()

            logger.info(f"获取配置股票 {len(config_stocks)} 只: {config_stocks[:5]}...")
            return config_stocks

        except Exception as e:
            logger.error(f"获取配置股票失败: {e}")
            return self._get_default_stocks()

    def _load_hold_stock_config(self) -> Dict:
        """加载持仓股票配置文件"""
        try:
            # 获取项目根目录
            current_dir = Path(__file__).parent
            project_root = current_dir.parent.parent
            hold_stock_file = project_root / "config" / "hold_stock.json"

            if not hold_stock_file.exists():
                logger.warning(f"持仓股票配置文件不存在: {hold_stock_file}")
                return {}

            with open(hold_stock_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            logger.info(f"成功加载持仓股票配置: {len(config.get('hold_stocks', []))} 只持仓股票")
            return config

        except Exception as e:
            logger.error(f"加载持仓股票配置失败: {e}")
            return {}

    def _get_default_stocks(self) -> List[str]:
        """获取默认股票列表"""
        try:
            # 从配置文件加载
            hold_config = self._load_hold_stock_config()
            hold_stocks = hold_config.get('hold_stocks', [])

            if hold_stocks:
                # 提取股票代码
                stock_symbols = [stock['symbol'] for stock in hold_stocks]
                logger.info(f"从配置文件获取持仓股票: {len(stock_symbols)} 只")
                return stock_symbols
            else:
                logger.info("配置文件中无持仓股票，返回空列表")
                return []

        except Exception as e:
            logger.error(f"从配置文件获取持仓股票失败: {e}")
            return []

    def get_all_stocks(self) -> List[Tuple[str, str]]:
        """
        获取所有股票列表 (兼容旧的stock_list.py功能)

        Returns:
            List[Tuple[str, str]]: 股票代码和名称的列表
        """
        try:
            hold_config = self._load_hold_stock_config()
            hold_stocks = hold_config.get('hold_stocks', [])

            if hold_stocks:
                # 转换为(symbol, name)格式
                return [(stock['symbol'], stock['name']) for stock in hold_stocks]
            else:
                logger.info("配置文件中无股票，返回空列表")
                return []

        except Exception as e:
            logger.error(f"获取所有股票列表失败: {e}")
            return []

    def get_fallback_stocks(self) -> List[Tuple[str, str]]:
        """
        获取备选股票列表（已废弃）

        Returns:
            List[Tuple[str, str]]: 空列表，不再使用备选股票
        """
        logger.warning("get_fallback_stocks已废弃，配置股票为空时表示无可用股票")
        return []

    def _perform_dynamic_selection(self) -> Tuple[List[Tuple[str, str]], Dict]:
        """
        执行动态选股

        Returns:
            (股票列表(symbol, name), 元数据)
        """
        try:
            logger.info("开始执行动态选股...")

            # 使用带统计数据的动态选股函数
            if self.config_manager:
                dynamic_stocks, stats = get_dynamic_stock_list_with_stats(self.config_manager)
            else:
                # 如果没有配置管理器，使用DynamicStockSelector的默认逻辑
                dynamic_stocks = []
                stats = {
                    'selection_method': 'no_config_manager',
                    'total_selected': 0,
                    'selection_time': datetime.now().isoformat(),
                    'sources': {},
                    'summary': {
                        'config': 0,
                        'longhu_bang': 0,
                        'social_media': 0,
                        'auto_discovery': 0
                    }
                }
                logger.warning("无配置管理器，跳过动态选股")

            logger.info(f"动态选股完成，共选择 {len(dynamic_stocks)} 只股票")
            return dynamic_stocks, stats

        except Exception as e:
            logger.error(f"动态选股失败: {e}")
            # 返回配置股票作为备选
            config_stocks = self._get_config_stocks()
            # 转换为(symbol, name)格式
            config_stock_tuples = [(stock, f"股票{stock}") for stock in config_stocks]
            metadata = {
                'selection_method': 'fallback_config',
                'total_selected': len(config_stock_tuples),
                'error': str(e),
                'selection_time': datetime.now().isoformat(),
                'sources': {
                    'config': len(config_stock_tuples),
                    'longhu_bang': 0,
                    'social_media': 0,
                    'auto_discovery': 0
                },
                'summary': {
                    'config': len(config_stock_tuples),
                    'longhu_bang': 0,
                    'social_media': 0,
                    'auto_discovery': 0
                }
            }
            return config_stock_tuples, metadata

    def get_selected_stocks(self, force_refresh: bool = False) -> Tuple[List[Tuple[str, str]], Dict]:
        """
        获取选中的股票列表

        Args:
            force_refresh: 是否强制刷新，忽略缓存

        Returns:
            (股票列表, 元数据信息)
        """
        try:
            # 如果强制刷新，直接执行选股
            if force_refresh:
                logger.info("强制刷新选股，忽略缓存")
                stocks, metadata = self._perform_dynamic_selection()
                self._save_cached_data(stocks, metadata)
                return stocks, metadata

            # 尝试加载缓存
            cached_data = self._load_cached_data()

            # 检查缓存是否有效
            if cached_data and self._is_cache_valid(cached_data):
                logger.info("使用缓存的选股结果")
                # 处理新旧格式的兼容性
                cached_stocks = cached_data['stocks']

                if cached_stocks:
                    # 检查是新格式（字典）还是旧格式（列表/元组）
                    if isinstance(cached_stocks[0], dict):
                        # 新格式：从字典中提取symbol和name
                        stock_tuples = [(stock['symbol'], stock['name']) for stock in cached_stocks]
                        logger.info("使用新格式缓存数据（包含详细信息）")
                    elif isinstance(cached_stocks[0], list):
                        # 旧格式：列表转元组
                        stock_tuples = [(stock[0], stock[1]) for stock in cached_stocks]
                        logger.info("使用旧格式缓存数据（仅包含代码和名称）")
                    else:
                        # 已经是元组格式
                        stock_tuples = cached_stocks
                        logger.info("使用元组格式缓存数据")

                    return stock_tuples, cached_data['metadata']
                else:
                    return [], cached_data['metadata']

            # 缓存无效或不存在，执行新的选股
            logger.info("缓存无效，执行新的动态选股")
            stocks, metadata = self._perform_dynamic_selection()

            # 保存到缓存
            self._save_cached_data(stocks, metadata)

            return stocks, metadata

        except Exception as e:
            logger.error(f"获取选股结果失败: {e}")
            # 返回配置股票作为最后的备选
            config_stocks = self._get_config_stocks()
            # 转换为(symbol, name)格式
            config_stock_tuples = [(stock, f"股票{stock}") for stock in config_stocks]
            fallback_metadata = {
                'selection_method': 'emergency_fallback',
                'total_selected': len(config_stock_tuples),
                'error': str(e),
                'selection_time': datetime.now().isoformat()
            }
            return config_stock_tuples, fallback_metadata

    def get_cache_info(self) -> Dict:
        """
        获取缓存信息

        Returns:
            缓存状态信息
        """
        try:
            if not self.cache_file.exists():
                return {
                    'cache_exists': False,
                    'cache_file': str(self.cache_file)
                }

            cached_data = self._load_cached_data()
            if not cached_data:
                return {
                    'cache_exists': True,
                    'cache_valid': False,
                    'cache_file': str(self.cache_file),
                    'error': 'Invalid cache format'
                }

            return {
                'cache_exists': True,
                'cache_valid': self._is_cache_valid(cached_data),
                'cache_file': str(self.cache_file),
                'cache_date': cached_data.get('date'),
                'stock_count': len(cached_data.get('stocks', [])),
                'selection_method': cached_data.get('metadata', {}).get('selection_method', 'unknown')
            }

        except Exception as e:
            return {
                'cache_exists': False,
                'error': str(e),
                'cache_file': str(self.cache_file)
            }

    def clear_cache(self):
        """清除缓存文件"""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                logger.info("缓存文件已清除")
            else:
                logger.info("缓存文件不存在，无需清除")
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")

    def refresh_stocks(self) -> Tuple[List[Tuple[str, str]], Dict]:
        """
        强制刷新股票选择

        Returns:
            (股票列表, 元数据信息)
        """
        return self.get_selected_stocks(force_refresh=True)

    def get_dynamic_stock_details(self) -> List[Dict]:
        """
        获取动态选股的详细信息（用于查看详情和迁移到常量股票池）

        Returns:
            包含详细信息的股票字典列表
        """
        try:
            cached_data = self._load_cached_data()
            if not cached_data:
                logger.warning("无缓存数据，执行新的选股")
                # 执行选股以生成缓存
                self.get_selected_stocks(force_refresh=True)
                cached_data = self._load_cached_data()

            if cached_data and cached_data.get('stocks'):
                stocks = cached_data['stocks']
                if stocks and isinstance(stocks[0], dict):
                    # 新格式，直接返回
                    return stocks
                else:
                    # 旧格式，需要增强
                    stock_tuples = [(s[0], s[1]) if isinstance(s, list) else s for s in stocks]
                    return self._enhance_stock_info(stock_tuples)

        except Exception as e:
            logger.error(f"获取动态选股详情失败: {e}")

        return []

    def migrate_to_hold_stock(self, symbols: List[str]) -> Dict:
        """
        将指定的股票从动态选股迁移到持仓股票池

        Args:
            symbols: 要迁移的股票代码列表

        Returns:
            迁移结果信息
        """
        try:
            # 获取动态选股的详细信息
            dynamic_stocks = self.get_dynamic_stock_details()
            dynamic_stock_map = {stock['symbol']: stock for stock in dynamic_stocks}

            # 加载当前持仓股票配置
            hold_config = self._load_hold_stock_config()
            if not hold_config:
                hold_config = {
                    "description": "持仓股票配置文件",
                    "version": "1.0",
                    "last_updated": str(date.today()),
                    "hold_stocks": [],
                    "config": {
                        "max_hold_stocks": 20,
                        "stock_validation": True,
                        "track_performance": True
                    }
                }

            # 获取现有的股票代码
            existing_symbols = {stock['symbol'] for stock in hold_config.get('hold_stocks', [])}

            # 准备迁移的股票
            migrated_stocks = []
            skipped_stocks = []

            for symbol in symbols:
                if symbol in existing_symbols:
                    skipped_stocks.append(symbol)
                    continue

                if symbol in dynamic_stock_map:
                    stock_info = dynamic_stock_map[symbol]
                    # 构建持仓股票格式
                    hold_stock = {
                        "symbol": stock_info['symbol'],
                        "name": stock_info['name'],
                        "market": stock_info['market'],
                        "sector": stock_info['sector'],
                        "reason": f"从动态选股迁移 - {stock_info['reason']}",
                        "purchase_date": date.today().strftime("%Y-%m-%d"),
                        "cost": 0.0
                    }
                    hold_config['hold_stocks'].append(hold_stock)
                    migrated_stocks.append(symbol)
                else:
                    logger.warning(f"股票 {symbol} 不在动态选股结果中")

            # 更新配置文件
            if migrated_stocks:
                hold_config['last_updated'] = str(date.today())

                # 保存更新后的配置
                hold_stock_file = Path(__file__).parent.parent.parent / "config" / "hold_stock.json"
                with open(hold_stock_file, 'w', encoding='utf-8') as f:
                    json.dump(hold_config, f, ensure_ascii=False, indent=2)

                logger.info(f"成功迁移 {len(migrated_stocks)} 只股票到持仓股票池")

            return {
                "success": True,
                "migrated_count": len(migrated_stocks),
                "migrated_stocks": migrated_stocks,
                "skipped_count": len(skipped_stocks),
                "skipped_stocks": skipped_stocks,
                "message": f"成功迁移 {len(migrated_stocks)} 只股票，跳过 {len(skipped_stocks)} 只已存在股票"
            }

        except Exception as e:
            logger.error(f"迁移股票到持仓股票池失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "migrated_count": 0,
                "migrated_stocks": [],
                "skipped_count": 0,
                "skipped_stocks": []
            }