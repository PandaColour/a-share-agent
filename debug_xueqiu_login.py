#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试雪球登录功能
检查登录页面结构和选择器问题
"""
import sys
import os
import asyncio
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_xueqiu_login_page():
    """测试雪球登录页面结构"""
    print("="*60)
    print("测试：雪球登录页面结构")
    print("="*60)

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            print("启动浏览器...")
            browser = await p.chromium.launch(headless=False)  # 使用非无头模式便于调试
            context = await browser.new_context()
            page = await context.new_page()

            print("访问雪球首页...")
            await page.goto("https://xueqiu.com", timeout=15000)
            await asyncio.sleep(3)

            print("检查当前页面标题:", await page.title())
            print("当前URL:", page.url)

            # 检查页面内容
            page_content = await page.content()
            print(f"页面内容长度: {len(page_content)}")

            # 查找登录相关元素
            login_elements = [
                ("登录链接", "//a[contains(@href, '/login')]"),
                ("登录按钮", "//button[contains(text(), '登录')]"),
                ("手机号输入", "input[name='phone']"),
                ("用户名输入", "input[name='username']"),
                ("密码输入", "input[type='password']"),
                ("提交按钮", "//button[contains(text(), '登录')]"),
                ("立即登录", "//button[contains(text(), '立即登录')]"),
                ("用户菜单", "//a[contains(@href, '/user')]"),
                ("退出按钮", "//span[contains(text(), '退出')]"),
            ]

            print("\n查找页面元素:")
            for name, selector in login_elements:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element:
                        text = await element.inner_text()
                        print(f"  ✅ {name}: 找到 (文本: '{text}')")
                    else:
                        print(f"  ❌ {name}: 未找到")
                except Exception as e:
                    print(f"  ❌ {name}: 错误 - {e}")

            # 检查是否有登录弹窗或模态框
            print("\n检查可能的登录弹窗:")
            modal_selectors = [
                "[class*='modal']",
                "[class*='dialog']",
                "[class*='popup']",
                "[role='dialog']",
                "[class*='login']"
            ]

            for selector in modal_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(f"  📋 {selector}: 找到 {len(elements)} 个元素")
                        for i, elem in enumerate(elements[:2]):  # 只显示前2个
                            try:
                                text = await elem.inner_text()
                                visible = await elem.is_visible()
                                print(f"    元素{i+1}: 可见={visible}, 文本='{text[:50]}...'")
                            except:
                                print(f"    元素{i+1}: 无法获取内容")
                except:
                    continue

            # 检查是否需要点击登录按钮
            print("\n尝试点击登录按钮...")
            click_selectors = [
                "//a[contains(@href, '/login')]",
                "//button[contains(text(), '登录')]",
                "[class*='login'] a",
                "[class*='login'] button"
            ]

            clicked = False
            for selector in click_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element:
                        await element.click()
                        print(f"  ✅ 点击了: {selector}")
                        clicked = True
                        await asyncio.sleep(3)
                        break
                except:
                    continue

            if not clicked:
                print("  ❌ 没有找到可点击的登录按钮")

            # 再次检查输入框（点击后可能出现）
            if clicked:
                print("\n点击后重新检查输入框:")
                input_selectors = [
                    "input[name='phone']",
                    "input[name='username']",
                    "input[type='text']",
                    "input[type='password']",
                    "input[placeholder*='手机']",
                    "input[placeholder*='账号']",
                    "input[placeholder*='用户']"
                ]

                for selector in input_selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            print(f"  📋 {selector}: 找到 {len(elements)} 个输入框")
                            for i, elem in enumerate(elements):
                                try:
                                    placeholder = await elem.get_attribute('placeholder')
                                    visible = await elem.is_visible()
                                    print(f"    输入框{i+1}: 可见={visible}, placeholder='{placeholder}'")
                                except:
                                    print(f"    输入框{i+1}: 无法获取属性")
                    except:
                        continue

            # 等待用户确认
            print("\n" + "="*60)
            print("请在浏览器中手动查看雪球页面")
            print("如果看到登录界面，请手动完成登录测试")
            print("按 Enter 键继续...")
            input()

            await browser.close()

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_login_with_credentials():
    """使用配置的凭据测试登录"""
    print("\n" + "="*60)
    print("测试：使用配置凭据登录")
    print("="*60)

    try:
        from config.config_manager import get_config

        config = get_config()
        web_config = config.get('analysis_settings.web_scraping', {})
        xueqiu_config = web_config.get('xueqiu_login', {})

        phone = xueqiu_config.get('phone', '').strip()
        password = xueqiu_config.get('password', '').strip()
        enabled = xueqiu_config.get('enabled', False)

        if not enabled:
            print("❌ 雪球登录未启用")
            return False

        if not phone or not password:
            print("❌ 雪球登录配置不完整")
            print(f"  手机号: {'已配置' if phone else '未配置'}")
            print(f"  密码: {'已配置' if password else '未配置'}")
            return False

        print(f"使用凭据登录:")
        print(f"  手机号: {phone[:3]}****{phone[-4:] if len(phone) > 7 else '****'}")
        print(f"  密码: {'*' * len(password)}")

        from src.data.web_scraper import WebScraper

        async with WebScraper(headless=False) as scraper:
            page = await scraper.browser.new_page()
            success = await scraper._ensure_xueqiu_login(page)

            if success:
                print("✅ 登录成功")

                # 检查登录状态
                is_logged_in = await scraper._check_xueqiu_login_status(page)
                print(f"登录状态检查: {'已登录' if is_logged_in else '未登录'}")

            else:
                print("❌ 登录失败")

            await page.close()
            return success

    except Exception as e:
        print(f"❌ 登录测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("雪球登录调试工具")
    print("检查登录页面结构和凭据配置")

    # 设置控制台编码
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass

    results = []

    # 运行测试
    results.append(("页面结构检查", await test_xueqiu_login_page()))
    results.append(("凭据登录测试", await test_login_with_credentials()))

    # 汇总结果
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)

    passed_count = sum(1 for _, result in results if result)
    total_count = len(results)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")

    print(f"\n总计: {passed_count}/{total_count} 通过")

    if passed_count == total_count:
        print("\n🎉 雪球登录功能正常！")
    else:
        print("\n❌ 雪球登录存在问题，需要修复")
        print("\n可能的解决方案:")
        print("1. 更新页面选择器以匹配雪球最新页面结构")
        print("2. 检查雪球是否更新了登录流程")
        print("3. 考虑使用官方API或其他数据源")

    return passed_count == total_count


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)