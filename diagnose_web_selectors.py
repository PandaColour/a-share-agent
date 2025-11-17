#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网页选择器诊断工具 - 用于检查网页实际DOM结构
"""
import asyncio
import sys
from playwright.async_api import async_playwright

async def diagnose_eastmoney(symbol: str = "002196"):
    """诊断东方财富页面结构"""
    print(f"\n{'='*60}")
    print(f"诊断东方财富页面: {symbol}")
    print(f"{'='*60}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 显示浏览器
        page = await browser.new_page()

        # 设置真实的浏览器headers
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })

        url = f"https://quote.eastmoney.com/{symbol}.html"
        print(f"访问: {url}")

        try:
            await page.goto(url, timeout=30000)
            print("✓ 页面加载成功\n")

            # 等待页面完全加载
            await asyncio.sleep(3)

            # 保存页面截图
            await page.screenshot(path=f'eastmoney_{symbol}.png')
            print("✓ 截图已保存: eastmoney_{symbol}.png\n")

            # 检查可能的新闻区域选择器
            print("检查新闻区域选择器:")
            selectors_to_test = [
                ".news-list",
                ".newslist",
                "#newslist",
                "[class*='news']",
                "[id*='news']",
                ".quote-news",
                "#quote-news",
                ".news-wrap",
                ".news-container",
                ".news",
                "ul[class*='news']",
                "div[class*='news']"
            ]

            found_selectors = []
            for selector in selectors_to_test:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        count = len(elements)
                        print(f"  ✓ '{selector}' - 找到 {count} 个元素")
                        found_selectors.append((selector, count))

                        # 获取第一个元素的HTML样本
                        if count > 0:
                            html = await elements[0].inner_html()
                            print(f"    HTML样本: {html[:100]}...")
                except Exception as e:
                    pass

            # 输出页面HTML结构（仅前5000字符）
            print("\n页面HTML结构样本:")
            html_content = await page.content()
            print(html_content[:5000])

            # 等待用户检查
            print("\n\n按Enter继续...")
            input()

        except Exception as e:
            print(f"✗ 错误: {e}")

        finally:
            await browser.close()


async def diagnose_xueqiu(symbol: str = "SZ002196"):
    """诊断雪球页面结构"""
    print(f"\n{'='*60}")
    print(f"诊断雪球页面: {symbol}")
    print(f"{'='*60}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # 设置真实的浏览器headers 避免被雪球拦截
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })

        url = f"https://xueqiu.com/S/{symbol}"
        print(f"访问: {url}")

        try:
            # 先访问雪球首页建立会话
            print("先访问雪球首页建立会话...")
            await page.goto("https://xueqiu.com", timeout=30000)
            await asyncio.sleep(2)  # 等待首页加载

            # 再访问目标股票页面
            print(f"访问目标页面: {url}")
            await page.goto(url, timeout=30000)
            print("✓ 页面加载成功\n")

            # 等待页面完全加载，模拟人类浏览行为
            print("等待页面完全加载...")
            await asyncio.sleep(5)

            # 保存页面截图
            await page.screenshot(path=f'xueqiu_{symbol}.png')
            print(f"✓ 截图已保存: xueqiu_{symbol}.png\n")

            # 检查可能的讨论区域选择器
            print("检查讨论区域选择器:")
            selectors_to_test = [
                ".timeline",
                ".feed-list",
                ".timeline__item",
                ".feed-item",
                "[class*='timeline']",
                "[class*='feed']",
                "[class*='post']",
                "[class*='comment']",
                "article",
                ".article-item",
                "div[class*='card']"
            ]

            found_selectors = []
            for selector in selectors_to_test:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        count = len(elements)
                        print(f"  ✓ '{selector}' - 找到 {count} 个元素")
                        found_selectors.append((selector, count))

                        # 获取第一个元素的HTML样本
                        if count > 0:
                            html = await elements[0].inner_html()
                            print(f"    HTML样本: {html[:100]}...")
                except Exception as e:
                    pass

            # 输出页面HTML结构（仅前5000字符）
            print("\n页面HTML结构样本:")
            html_content = await page.content()
            print(html_content[:5000])

            # 等待用户检查
            print("\n\n按Enter继续...")
            input()

        except Exception as e:
            print(f"✗ 错误: {e}")

        finally:
            await browser.close()


async def main():
    """主函数"""
    print("\n网页选择器诊断工具")
    print("="*60)

    choice = input("\n选择要诊断的网站:\n1. 东方财富\n2. 雪球\n3. 两者都诊断\n\n请选择 (1/2/3): ")

    if choice == '1':
        symbol = input("输入股票代码 (默认 002196): ").strip() or "002196"
        await diagnose_eastmoney(symbol)
    elif choice == '2':
        symbol = input("输入股票代码 (默认 SZ002196): ").strip() or "SZ002196"
        await diagnose_xueqiu(symbol)
    elif choice == '3':
        symbol = input("输入股票代码 (默认 002196): ").strip() or "002196"
        await diagnose_eastmoney(symbol)

        if symbol.startswith('6'):
            xq_symbol = f"SH{symbol}"
        elif symbol.startswith('0') or symbol.startswith('3'):
            xq_symbol = f"SZ{symbol}"
        else:
            xq_symbol = symbol

        await diagnose_xueqiu(xq_symbol)
    else:
        print("无效选择")


if __name__ == "__main__":
    asyncio.run(main())
