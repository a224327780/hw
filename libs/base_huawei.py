import asyncio
import json
import os
import random
import string
import time
from pathlib import Path

import requests
from pyppeteer.network_manager import Response, Request

from libs.base import BaseClient

name_map = {
    '项目管理': [['week_new_project', 0]],
    '代码托管': [['week_new_git', 0], ['open_code_task', 1], ['push_code_task', 2]],
    'CloudIDE': [['open_ide_task', 0]],
    '代码检查': [['week_new_code_check', 0], ['check_code_task', 1]],
    '编译构建': [['week_new_compile_build', 0], ['compile_build_task', 1]],
    '部署': [['deploy_task', 1]],
    '发布': [['upload_task', 0]],
    '流水线': [['week_new_pipeline', 0], ['pipeline_task', 1]],
    '接口测试': [['week_new_api_test_task', 0], ['api_test_task', 1]],
    '测试管理': [['new_test_task', 0]],
    'APIG网关': [
        ['new_new_api_task', 0],
        ['run_api_task', 1]],
    '函数工作流': [['new_fun_task', 0]],
    '使用API  Explorer完在线调试': 'api_explorer_task',
    '使用API Explorer在线调试': 'api_explorer_task',
    '使用Devstar生成代码工程': 'dev_star_task',
    '浏览Codelabs代码示例': 'view_code_task',
    '体验DevStar快速生成代码': 'fast_dev_star',
}

init_name_map = {
    # '项目管理': [['week_new_project', 0]],
    # '代码托管': [['week_new_git', 0]],
    # '代码检查': [['week_new_code_check', 0]],
    # '编译构建': [['week_new_compile_build', 0]],
    # '部署': [['week_new_deploy', 0]],
    # '流水线': [['week_new_pipeline', 0]],
    '使用API  Explorer完在线调试': 'api_explorer_task',
    '使用API Explorer在线调试': 'api_explorer_task',
    # '使用Devstar生成代码工程': 'dev_star_task',
}


class BaseHuaWei(BaseClient):

    def __init__(self):
        super().__init__()
        self.url = 'https://auth.huaweicloud.com/authui/login.html?service=https%3A%2F%2Fdevcloud.huaweicloud.com%2Fbonususer%2Fhome&quickLogin=true#/login2'
        self.task_page = None
        self.create_done = True
        self.cancel = False
        self.task_page_url = 'https://devcloud.huaweicloud.com/bonususer/home/makebonus'
        self.sign_url = 'https://devcloud.huaweicloud.com/bonususer/home/converge'
        self.domain = 'https://devcloud.cn-north-4.huaweicloud.com'
        self.cookies = None
        self.cftk = None
        self.user_id = None
        self.projects = None

    async def after_run(self, **kwargs):
        credit = await self.get_credit()
        username = self.username
        self.logger.warning(f"{username} -> {credit}\n")

        if credit and type(credit) == str:
            credit = int(credit.replace('码豆', '').strip())

        if credit and type(credit) == int and credit > 0:
            _id = f'{self.parent_user}_{username}' if self.parent_user else self.username
            cookies = '' if not self.cookies else "; ".join([str(x) + "=" + str(y) for x, y in self.cookies.items()])
            data = {'name': _id, 'credit': credit, 'cookies': cookies}
            if self.user_id:
                data['uid'] = self.user_id
            requests.post(f'{self.api}/huawei/save', json=data)

    async def start(self):
        if self.page.url != self.task_page_url:
            await self.page.goto(self.task_page_url, {'waitUntil': 'load'})

        id_list = ['experience-missions', 'middleware-missions']
        for _id in id_list:
            try:
                await self.execute(_id, 'ul.devui-nav li.ng-star-inserted', '', True, name_map)
            except Exception as e:
                self.logger.debug(e)

        try:
            await self.regular()
        except Exception as e:
            self.logger.debug(e)

        # try:
        #     await self.init_account()
        # except Exception as e:
        #     self.logger.debug(e)

    async def regular(self):
        await self.execute('regular-missions', '.daily-list li', 'feedback-', False, name_map)

    async def init_account(self):
        # await self.execute('experience-missions', 'ul.devui-nav li.ng-star-inserted', '', True, init_name_map)

        await self.page.goto('https://devcloud.huaweicloud.com/bonususer/home/new', {'waitUntil': 'load'})
        await asyncio.sleep(2)
        await self.execute('new-tasks-box', 'li.hot-task-item', 'new-task', False, init_name_map)

    async def execute(self, element_id, element_list_name, task_node, is_tab=True, task_map=None):
        elements = await self.page.querySelectorAll(f'#{element_id} {element_list_name}')
        for i, element in enumerate(elements):
            if self.cancel:
                break

            if is_tab:
                name = str(await element.Jeval('a', 'el => el.textContent')).strip()
                task_list = task_map.get(name)
                if task_list is None:
                    continue

                for task in task_list:
                    await element.click()
                    await asyncio.sleep(1)
                    task_node = f'#{element_id} #{element_id}-{task[1]}'
                    await self.run_task(task_node, task[0])
            else:
                _task_node = f'#{element_id} #{task_node}{i}'
                task_name = str(await self.page.Jeval(f'{_task_node} h5', 'el => el.textContent')).strip()
                if not task_map.get(task_name):
                    continue

                await self.run_task(_task_node, task_map.get(task_name))

    async def is_done(self, node, task_fun):
        try:
            is_done = await self.page.querySelector(f"{node} .complate-img")
            if is_done:
                # if 'week' in task_fun:
                #     return False
                return True

            is_done = await self.page.querySelector(f"{node} img.completed")
            if is_done:
                # if 'week' in task_fun:
                #     return False
                return True
        except Exception as e:
            self.logger.debug(e)
        return False

    async def run_task(self, task_node, task_fun):
        task_name = await self.page.Jeval(f'{task_node} h5', 'el => el.textContent')

        if await self.is_done(task_node, task_fun):
            self.logger.warning(f'{task_name} -> DONE.')
            return True

        await self.page.click(task_node)
        await asyncio.sleep(2)
        self.logger.info(f'{task_name}')

        try:
            self.task_page = await self.get_new_page()
            await self.task_page.setUserAgent(self.ua)
        except Exception as e:
            self.logger.error(e)
            raise e

        try:
            func = getattr(self, task_fun)
            # await func()
            await asyncio.wait_for(func(), timeout=100.0)
            self.logger.warning(f'{task_name} -> DONE.')

            if task_fun == 'week_new_project':
                await self.get_projects()
        except Exception as e:
            self.logger.error(e)
        finally:
            await self.close_page()
            await asyncio.sleep(2)
            return True

    async def get_credit(self):
        for i in range(3):
            if self.page.url != self.sign_url:
                await self.page.goto(self.sign_url, {'waitUntil': 'load'})
            else:
                await self.page.reload({'waitUntil': 'load'})

            await asyncio.sleep(3)
            await self.close_modal()
            try:
                s = await self.page.Jeval('#homeheader-coins .bonus-count', 'el => el.textContent')
                return str(s).replace('码豆', '').strip()
            except Exception as e:
                self.logger.debug(e)
        return 0

    async def sign_task(self):
        try:
            await self.page.goto(self.sign_url, {'waitUntil': 'load'})
            await asyncio.sleep(5)
            await self.close_modal()
            info = await self.page.Jeval('#homeheader-signin','el => el.textContent')
            sign_txt = str(info).strip()
            self.logger.info(sign_txt)
            if sign_txt.find('已签到') == -1:
                await self.page.click('#homeheader-signin')
                await asyncio.sleep(3)
        except Exception as e:
            self.logger.warning(e)

    async def close_modal(self):
        try:
            await self.page.click('#rule-dialog .close-btn')
            await asyncio.sleep(1)
        except Exception as e:
            self.logger.debug(e)

    async def get_new_page(self):
        await asyncio.sleep(2)
        await self.page.click('.modal.in .modal-footer .devui-btn')
        await asyncio.sleep(5)
        page_list = await self.browser.pages()
        await page_list[-1].setViewport({'width': self.width + 560, 'height': self.height})
        return page_list[-1]

    async def close_page(self):
        page_list = await self.browser.pages()
        if len(page_list) > 1:
            page = page_list[-1]
            if page.url != self.task_page_url:
                await page.close()

    async def api_explorer_task(self):
        await asyncio.sleep(2)
        html = str(await self.task_page.JJeval('.userInfo', '(els) => els.map(el => el.outerHTML)'))
        if html.find('English') != -1:
            items = await self.task_page.querySelectorAll('.userInfo')
            await items[1].hover()
            await asyncio.sleep(2)
            await self.task_page.click('.cdk-overlay-container .dropdown-item')
            await asyncio.sleep(5)

        url = 'https://apiexplorer.developer.huaweicloud.com/apiexplorer/overview'
        if self.task_page.url == url:
            url = 'https://apiexplorer.developer.huaweicloud.com/apiexplorer/doc?product=DevStar&api=ListPublishedTemplates'
            await self.task_page.goto(url, {'waitUntil': 'load'})
            await asyncio.sleep(3)

        await self.task_page.click('#debug')
        await asyncio.sleep(3)

    async def api2_explorer_task(self):
        _url = 'https://apiexplorer.developer.huaweicloud.com/apiexplorer/doc?product=DevStar&api=ListPublishedTemplates'
        await self.task_page.goto(_url, {'waitUntil': 'load'})
        await self.api_explorer_task()

    async def dev_star_task(self):
        await asyncio.sleep(2)
        await self.task_page.waitForSelector('#confirm-download-btn', {'visible': True})
        await self.task_page.click('.template-dynamic-paramter-title .devui-btn')
        await asyncio.sleep(2)
        await self.task_page.click('#confirm-upload-btn')
        await asyncio.sleep(3)

    async def view_code_task(self):
        await asyncio.sleep(10)
        await self.task_page.click('#code-template-cards .card-width:nth-child(2) .code-template-card-title')
        await asyncio.sleep(2)

    async def open_code_task(self):
        await asyncio.sleep(3)
        self.git = await self.get_git_url(self.task_page)
        self.logger.info(self.git)
        items = await self.task_page.querySelectorAll(
            '.selfcodehubhead-right-items .selfcodehubhead-right-item .devui-btn')
        if items and len(items):
            await items[3].click()
            await asyncio.sleep(20)

    async def open_ide_task(self):
        await asyncio.sleep(5)
        try:
            await self.task_page.click('.devui-checkbox')
            await asyncio.sleep(3)
            await self.task_page.click('.devui-btn-danger')
        except:
            pass

        try:
            await self.task_page.click('.region-modal-button-content .region-modal-button-common')
            await asyncio.sleep(3)
        except Exception as e:
            self.logger.debug(e)

        await self.task_page.click(
            '.trial-stack-info .trial-stack:nth-child(1) .stack-content .stack-position .devui-btn')
        await asyncio.sleep(10)

    async def push_code_task(self):
        if not self.git:
            page = await self.browser.newPage()
            await page.goto(f'{self.domain}/codehub/home', {'waitUntil': 'load'})
            await asyncio.sleep(5)
            self.git = await self.get_git_url(page)

        self.logger.info(self.git)
        if self.git:
            now_time = time.strftime('%Y-%m-%d %H:%M:%S')
            repo_name = Path(self.git).stem
            cmd = [
                'cd /tmp',
                'git config --global user.name "caoyufei" && git config --global user.email "atcaoyufei@gmail.com"',
                f'git clone {self.git}',
                f'cd /tmp/{repo_name}',
                f'echo "{now_time}" >> time.txt',
                "git add .",
                "git commit -am 'time'",
                "git push origin master",
            ]
            os.system(' && '.join(cmd))
            os.system(f'rm -rf /tmp/{repo_name}')
            await asyncio.sleep(1)

    async def week_new_compile_build(self):
        await asyncio.sleep(2)
        await self.task_page.waitForSelector('.devui-layout-main-content', {'visible': True})
        await self.task_page.click('.devui-layout-main-content #create_new_task')
        await asyncio.sleep(1)
        await self.task_page.click('.button-group .devui-btn-stress')
        await asyncio.sleep(5)
        template = await self.task_page.querySelectorAll('.template-content li.template-item')
        await template[3].click()
        await asyncio.sleep(1)
        await self.task_page.click('.button-group .devui-btn-stress')

        await asyncio.sleep(5)
        card_list = await self.task_page.querySelectorAll('.task-detail-cardlist .card-li')
        await card_list[2].hover()
        await asyncio.sleep(1)
        await self.task_page.click('.task-detail-cardlist .card-li:nth-child(3) .add-btn')
        await asyncio.sleep(2)
        await self.task_page.click('.button-group .devui-btn-stress')
        await asyncio.sleep(2)

    async def compile_build_task(self):
        await self.check_code_task()

    async def check_code_task(self):
        await asyncio.sleep(5)
        task_list = await self.task_page.querySelectorAll('.devui-table tbody tr .devui-btn-primary')
        if task_list and len(task_list):
            await task_list[0].click()
            await asyncio.sleep(3)
            try:
                await self.task_page.click('.modal.in .devui-btn-primary')
            except Exception as e:
                self.logger.debug(e)
        await asyncio.sleep(2)

    async def run_test_task(self):
        await asyncio.sleep(5)
        try:
            await self.task_page.click('#global-guidelines .icon-close')
        except Exception as e:
            self.logger.debug(e)

        await self.task_page.waitForSelector('div.devui-table-view', {'visible': True})
        await self.task_page.evaluate(
            '''() =>{ document.querySelector('div.devui-table-view tbody tr:nth-child(1) td:nth-child(12) i.icon-run').click(); }''')

    async def week_new_deploy(self):
        await asyncio.sleep(2)
        await self.task_page.waitForSelector('.devui-layout-operate', {'visible': True})
        await self.task_page.click('.devui-layout-operate #taskCreate')
        await asyncio.sleep(1)
        await self.task_page.click('.step-group .devui-btn-stress')
        await asyncio.sleep(5)

        template_list = await self.task_page.querySelectorAll('.template-list .template-item')
        await template_list[1].click()
        await asyncio.sleep(0.5)
        await self.task_page.click('.step-group .devui-btn-stress')
        await asyncio.sleep(3)
        items = await self.task_page.querySelectorAll('.category-wrapper ul.devui-nav li')
        await items[4].click()
        await asyncio.sleep(3)

        card_list = await self.task_page.querySelectorAll('.task-detail-cardlist .card-li')
        await card_list[0].hover()
        await asyncio.sleep(0.5)
        await self.task_page.click('.task-detail-cardlist .card-li:nth-child(1) .add-btn')
        await asyncio.sleep(1)

        link_list = await self.task_page.querySelectorAll('.marked-text .devui-link')
        await link_list[1].click()

        await asyncio.sleep(10)
        page_list = await self.browser.pages()
        await page_list[-1].setViewport({'width': self.width, 'height': self.height})
        new_page = page_list[-1]
        await asyncio.sleep(2)
        await new_page.type('input.input-textarea-cn', self.username)
        await asyncio.sleep(0.5)
        await new_page.click('.btn-box .devui-btn-stress')
        await asyncio.sleep(2)
        await new_page.close()

        await self.task_page.click('#DeploymentGroup_groupId_button')
        await asyncio.sleep(2)
        await self.task_page.click('.deployment-select')
        await asyncio.sleep(0.5)
        await self.task_page.click('.devui-dropdown-item:nth-child(1)')
        await asyncio.sleep(0.5)
        await self.task_page.type('div#SingleLineText_port_to_stop input', ''.join(random.choices(string.digits, k=4)))
        await asyncio.sleep(0.5)
        await self.task_page.click('.deployman-create-content__button-group .devui-btn-primary')
        await asyncio.sleep(3)

    async def deploy_task(self):
        await asyncio.sleep(3)
        await self.task_page.click('#rf-task-execute')
        await asyncio.sleep(3)

    async def run_test(self):
        await self._close_test()
        await self.task_page.waitForSelector('div.devui-table-view', {'visible': True})
        # string = await self.task_page.Jeval('div.devui-table-view tbody tr:nth-child(1) td:nth-child(12)',
        #                                     'el => el.outerHTML')
        # print(string)

        await self.task_page.evaluate(
            '''() =>{ document.querySelector('div.devui-table-view tbody tr:nth-child(1) td:nth-child(12) i.icon-run').click(); }''')

        await asyncio.sleep(5)

    async def api_test_task(self):
        await asyncio.sleep(2)
        await self._close_test()
        await self._tab_api_test()
        await self.task_page.evaluate(
            '''() =>{ document.querySelector('div.devui-table-view tbody tr:nth-child(1) i.icon-run').click(); }''')
        await asyncio.sleep(5)

    async def week_new_pipeline(self):
        await asyncio.sleep(2)
        await self.task_page.click('#createPipeline')
        await asyncio.sleep(1)
        await self.task_page.click('.content .devui-dropup')
        await asyncio.sleep(0.5)
        await self.task_page.click('.devui-dropdown-item:nth-child(1)')
        await asyncio.sleep(0.5)
        await self.task_page.click('.pipeline-edit-tab .devui-btn-primary')
        await asyncio.sleep(0.5)

        dropdowns = await self.task_page.querySelectorAll('.devui-dropup')
        for dropdown in dropdowns:
            await dropdown.click()
            await asyncio.sleep(1)
            dropdown_item = await dropdown.querySelectorAll('.devui-dropdown-item')
            await dropdown_item[0].click()
            await asyncio.sleep(0.5)

        await self.task_page.click('.pipeline-edit-tab .devui-btn-primary')
        await asyncio.sleep(1)
        await self.task_page.click('.pipeline-edit-tab .devui-btn-primary')
        await asyncio.sleep(5)

    async def pipeline_task(self):
        await asyncio.sleep(5)
        items = await self.task_page.querySelectorAll('div.devui-table-view tbody tr .pipeline-run')
        if len(items) <= 0:
            return

        await items[0].click()
        await asyncio.sleep(3)

        items = await self.task_page.querySelectorAll('.modal.in .devui-btn-primary')
        if len(items) > 0:
            await items[0].click()
            await asyncio.sleep(2)
        items = await self.task_page.querySelectorAll('.modal.in .devui-btn-primary')
        if len(items) > 0:
            await items[0].click()
        await asyncio.sleep(5)

    async def new_project(self):
        self.logger.info(f'create project {self.username}')
        url = f'{self.domain}/home/projectSeries'
        page = await self.get_new_win_page(url)
        try:
            await asyncio.sleep(2)
            await page.click('#projet_phoenix')
            await asyncio.sleep(1)
            try:
                await page.click('.icon-close')
                await asyncio.sleep(1)
            except:
                pass

            await page.type('#projectCreateFormProjectName', self.username)
            await asyncio.sleep(0.5)
            await page.click('#createProjectBtn')
            await asyncio.sleep(3)
        except Exception as e:
            raise e
        finally:
            await page.close()

    async def week_new_git(self):
        await asyncio.sleep(5)
        await self.task_page.click('.devui-btn-primary')
        await asyncio.sleep(1)
        git_name = ''.join(random.choices(string.ascii_letters, k=6))
        await self.task_page.type('#rname', git_name)
        await asyncio.sleep(0.5)

        btn_list = await self.task_page.querySelectorAll('.new-repo-row-center:nth-child(1) .devui-checkbox')
        await btn_list[2].click()

        await self.task_page.click('#newAddRepoBtn')
        await asyncio.sleep(5)

        # self.git = await self.get_git(self.task_page)
        # self.logger.info(self.git)

    async def get_git_url(self, page):
        git_list = await page.querySelectorAll('.devui-table tbody tr .avatar-img')
        if git_list and len(git_list):
            await git_list[0].click()
            await asyncio.sleep(5)
            await page.waitForSelector('.repo-info-right', {'visible': True})
            await page.click('.selfcodehubhead-right-item .devui-dropdown')
            await asyncio.sleep(1)
            git_url = await page.Jeval('.clone-url .url', "el => el.getAttribute('title')")
            _user = self.parent_user if self.parent_user else self.username
            git_url = git_url.replace('git@', f'https://{_user}%2F{self.username}:{self.password}@')
            return git_url.replace('com:', 'com/')
        return None

    async def week_new_code_check(self):
        try:
            await self.task_page.waitForSelector('.pull-right', {'visible': True})
            await self.task_page.click('.pull-right .devui-btn-primary')
            await self.task_page.waitForSelector('#codecheck-new-task-btn-0', {'visible': True})
            await self.task_page.click('#codecheck-new-task-btn-0')
            await asyncio.sleep(5)
        except Exception as e:
            self.logger.exception(e)

    async def upload_task(self):
        await asyncio.sleep(3)
        # items = await self.task_page.querySelectorAll('')

        await self.task_page.click('#releasemanUploadDrop tbody tr:nth-child(1) td a.column-link')
        await asyncio.sleep(3)
        await self.task_page.waitForSelector('#upload_file', {'visible': True})
        f = await self.task_page.querySelector('#releaseman-file-select')
        await f.uploadFile(__file__)
        await asyncio.sleep(3)

    async def new_test_task(self):
        await asyncio.sleep(3)
        try:
            await self.task_page.click('#global-guidelines .icon-close')
        except Exception as e:
            self.logger.debug(e)

        await asyncio.sleep(3)

        try:
            await self.task_page.click('.devui-step-item .icon-close')
        except Exception as e:
            self.logger.debug(e)

        await asyncio.sleep(1)
        await self.task_page.waitForSelector('div.create-case', {'visible': True})
        await self.task_page.click('div.create-case')
        await asyncio.sleep(5)
        await self.task_page.type('#caseName', ''.join(random.choices(string.ascii_letters, k=6)))
        await self.task_page.click('div.footer .devui-btn-stress')
        await asyncio.sleep(5)

    async def week_new_api_test_task(self):
        await asyncio.sleep(2)
        await self._close_test()
        await self._tab_api_test()
        await self.task_page.waitForSelector('div.create-case', {'visible': True})
        await self.task_page.click('div.create-case')
        await asyncio.sleep(2)
        await self.task_page.type('#caseName', ''.join(random.choices(string.ascii_letters, k=6)))
        await self.task_page.click('div.footer .devui-btn-stress')
        await asyncio.sleep(3)

    async def week_new_project(self):
        await asyncio.sleep(5)
        try:
            notice = await self.task_page.querySelector('#declaration-notice')
            if notice:
                btn_list = await self.task_page.querySelectorAll('.quick-create-phoenix .devui-btn')
                await btn_list[1].click()
                await asyncio.sleep(1)
                await self.task_page.click('#declaration-notice div.devui-checkbox label')
                await asyncio.sleep(1)
                await self.task_page.click('#declaration-notice .devui-btn.devui-btn-primary')
                await asyncio.sleep(1)
        except Exception as e:
            self.logger.debug(e)

        try:
            btn_list = await self.task_page.querySelectorAll('.quick-create-phoenix .devui-btn')
            await btn_list[0].click()
            await asyncio.sleep(2)
        except Exception as e:
            await self.send_photo(self.task_page, 'week_new_project')
            raise e

    async def new_new_api_task(self):
        await asyncio.sleep(15)
        self.logger.debug(self.task_page.url)

    async def run_api_task(self):
        await asyncio.sleep(3)
        await self.task_page.click('div.ti-intro-modal .ti-btn-danger')
        await asyncio.sleep(3)
        await self.task_page.click('#send')
        await asyncio.sleep(2)
        await self.task_page.click('.pull-left .cti-button')
        await asyncio.sleep(5)
        await self.task_page.click('.pull-right.mr10.cti-button')
        await asyncio.sleep(5)
        await self.task_page.click('.ti-btn-danger.ml10.ng-binding')

    async def new_fun_task(self):
        url = self.task_page.url
        if url.find('serverless/dashboard') == -1:
            url = f'{url}#/serverless/dashboard'
            await self.task_page.goto(url, {'waitUntil': 'load'})

        await asyncio.sleep(2)
        try:
            await self.task_page.click('#rightWrap .ant-row .ant-btn')
            await asyncio.sleep(3)
            await self.task_page.type('#name', ''.join(random.choices(string.ascii_letters, k=6)), {'delay': 30})
            await asyncio.sleep(3)
            await self.task_page.click('.preview .ant-btn-primary')
            await asyncio.sleep(5)
        except Exception as e:
            self.logger.warning(e)
        finally:
            return

    async def fast_dev_star(self):
        await asyncio.sleep(5)
        await self.task_page.click('.code-template-codebase-right-operations-panel .devui-btn-common')
        # await asyncio.sleep(1)
        # await self.task_page.click('.operation-next')
        await asyncio.sleep(3)
        await self.task_page.click('#deploy-btn')

        await asyncio.sleep(15)

    async def delete_function(self):
        page = await self.browser.newPage()
        await page.setViewport({'width': self.width, 'height': self.height})
        await page.setUserAgent(self.ua)
        url_list = ['https://console.huaweicloud.com/functiongraph/?region=cn-south-1#/serverless/functionList',
                    'https://console.huaweicloud.com/functiongraph/?region=cn-north-4#/serverless/functionList']

        try:
            for _url in url_list:
                await page.goto(_url, {'waitUntil': 'load'})
                try:
                    await page.waitForSelector('.ti3-action-menu-item', {'timeout': 10000})
                except Exception as e:
                    self.logger.debug(e)
                    continue

                elements = await page.querySelectorAll('a.ti3-action-menu-item')
                if not elements or not len(elements):
                    self.logger.info('no functions.')
                    break

                for i in range(8):
                    for element in elements:
                        s = await element.Jeval('section', 'el => el.textContent')
                        if s in ['Delete', '删除']:
                            _id = str(await (await element.getProperty('id')).jsonValue())
                            try:
                                await element.click()
                                self.logger.info(f'delete function {_id}.')
                                # await page.evaluate('''() =>{ document.querySelector('#%s').click(); }''' % _id)
                                await asyncio.sleep(1)

                                _input = await page.querySelector('.modal-confirm-text input[type="text"]')
                                if not _input:
                                    await asyncio.sleep(1)
                                    continue

                                await page.type('.modal-confirm-text input[type="text"]', 'DELETE', {'delay': 10})
                                await asyncio.sleep(0.5)
                                await page.click('.ti3-modal-footer .ti3-btn-middle')
                                await asyncio.sleep(1)

                                buttons = await page.querySelectorAll('.ti3-modal-footer [type="button"]')
                                if buttons and len(buttons):
                                    await buttons[1].click()
                                    await asyncio.sleep(2)

                            except Exception as e:
                                self.logger.error(e)
                            break
                    elements = await page.querySelectorAll('a.ti3-action-menu-item')

        finally:
            await page.close()
            await asyncio.sleep(1)

    async def delete_project(self):
        page = await self.get_new_win_page(None)
        try:
            for item in self.projects:
                self.logger.warning(f"delete project {item['name']}")
                delete_url = f"{self.domain}/projects/project/{item['project_id']}/config/info"
                try:
                    await page.goto(delete_url, {'waitUntil': 'load'})
                    await asyncio.sleep(2)
                    btn_list = await page.querySelectorAll('.margin-right-s .devui-btn-common')
                    await btn_list[0].click()
                    await asyncio.sleep(1)
                    # await page.click('.form-container .margin-right-s .devui-btn:nth-child(1)')
                    # await asyncio.sleep(2)
                    await page.type('.projectInput', item['name'])
                    await asyncio.sleep(0.5)
                    await page.click('.dialog-footer .devui-btn-primary')
                    await asyncio.sleep(2)
                except Exception as e:
                    self.logger.error(e)
        except Exception as e:
            self.logger.error(e)
        finally:
            await page.close()

    async def delete_api(self):
        page = await self.browser.newPage()
        try:
            await page.goto('https://console.huaweicloud.com/apig/?region=cn-north-4#/apig/multiLogical/openapi/list',
                            {'waitUntil': 'load'})
            await page.setViewport({'width': self.width, 'height': self.height})
            await asyncio.sleep(5)
            elements = await page.querySelectorAll('#openapi_list tr')
            if len(elements) <= 0:
                return

            await page.click('#openapi_list tr:nth-child(1) th:nth-child(1)')
            await asyncio.sleep(0.5)

            # 下线
            try:
                await page.click('.apiList-groups .cti-button:nth-child(3) .cti-btn-container')
                await asyncio.sleep(1)
                await page.click('.ti-modal-dialog .cti-button:nth-child(1) .cti-btn-container')
                await asyncio.sleep(2)
            except Exception as e:
                self.logger.debug(e)
                await page.click('#openapi_list tr:nth-child(1) th:nth-child(1)')
                await asyncio.sleep(0.5)

            # 删除
            await page.click('#openapi_list tr:nth-child(1) th:nth-child(1)')
            await asyncio.sleep(0.5)
            await page.click('.apiList-groups .cti-button:nth-child(4) .cti-btn-container')
            await asyncio.sleep(3)
            await page.type('#deleteContent-text', 'DELETE')
            await asyncio.sleep(0.5)
            await page.click('.ti-modal-dialog .cti-button:nth-child(1) .cti-btn-container')
            await asyncio.sleep(2)
        except Exception as e:
            self.logger.debug(e)
        finally:
            await page.close()

    async def delete_api_group(self):
        page = await self.browser.newPage()
        try:
            await page.goto('https://console.huaweicloud.com/apig/?region=cn-north-4#/apig/multiLogical/openapi/group',
                            {'waitUntil': 'load'})
            await page.setViewport({'width': self.width, 'height': self.height})
            await asyncio.sleep(8)
            elements = await page.querySelectorAll('#openapi_group tbody tr')
            if len(elements) < 1:
                return

            await page.click('#openapi_group tbody tr:nth-child(1) td:nth-child(1) a')
            await asyncio.sleep(2)
            await page.click('.cti-fl-right .cti-button:nth-child(4) .cti-btn-container')
            await asyncio.sleep(1)
            await page.type('#tiny-text', 'DELETE')
            await asyncio.sleep(0.5)
            await page.click('#delG')
            await asyncio.sleep(2)
        except Exception as e:
            self.logger.debug(e)
        finally:
            await page.close()

    async def _close_test(self):
        try:
            await asyncio.sleep(2)
            await self.task_page.click('#global-guidelines .icon-close')
            await asyncio.sleep(2)
        except Exception as e:
            self.logger.debug(e)

        try:
            await self.task_page.click('.devui-step-item .icon-close')
            await asyncio.sleep(1)
        except Exception as e:
            self.logger.debug(e)

    async def _tab_api_test(self):
        await asyncio.sleep(1)
        await self.task_page.waitForSelector('#testtype_1')
        await self.task_page.click('#testtype_1')
        await asyncio.sleep(1)

    async def sign_post(self):
        tid_list = [87703, 87513, 87948, 87424, 87445, 87587, 87972, 87972]
        n = random.randint(1, 2)
        for i in range(n):
            tid = random.choice(tid_list)
            await self.page.goto(f'https://bbs.huaweicloud.com/forum/thread-{tid}-1-1.html', {'waitUntil': 'load'})
            await self.page.waitForSelector('#fastpostsubmit')
            content = random.choice(
                ['666', '回帖送码豆', '论坛回帖送码豆喽'])
            await self.page.evaluate(
                '''() =>{ ue.setContent('<p>%s</p>'); }''' % content)
            await asyncio.sleep(1)
            await self.page.click('#fastpostsubmit')
            await asyncio.sleep(5)

    async def post_reply(self):
        await self.page.goto('https://bbs.huaweicloud.com/forum/thread-89722-1-1.html', {'waitUntil': 'load'})
        await self.page.waitForSelector('#fastpostsubmit')
        content = '#2020年终盛典# 我很期待这次盛典，祝盛典圆满成功！顺利召开！'
        await self.page.evaluate(
            '''() =>{ ue.setContent('<p>%s</p>'); }''' % content)
        await asyncio.sleep(1)
        await self.page.click('#fastpostsubmit')
        await asyncio.sleep(10)

        await self.page.goto('https://bbs.huaweicloud.com/forum/thread-89742-1-1.html', {'waitUntil': 'load'})
        await self.page.waitForSelector('#fastpostsubmit')
        content = ' #我和华为云的这一年#这一年是我和华为云相识的第一年，知道了华为云有很多课程，大拿讲课，受益颇丰。'
        await self.page.evaluate(
            '''() =>{ ue.setContent('<p>%s</p>'); }''' % content)
        await asyncio.sleep(1)
        await self.page.click('#fastpostsubmit')
        await asyncio.sleep(5)

        # await self.page.goto('https://bbs.huaweicloud.com/forum/thread-80376-1-1.html', {'waitUntil': 'load'})
        # await self.page.waitForSelector('#fastpostsubmit')
        # await self.page.evaluate('''() =>{ document.querySelector('#tabeditor-2').click(); }''')
        # await asyncio.sleep(1)
        # await self.page.click('#tabeditor-2')
        # content = random.choice(
        #     [
        #         '![1024](https://bbs-img-cbc-cn.obs.cn-north-1.myhuaweicloud.com/data/attachment/forum/202010/09/204951b8y0xls2nopvc6az.png)',
        #         '![1024](https://bbs-img-cbc-cn.obs.cn-north-1.myhuaweicloud.com/data/attachment/forum/202010/09/161504wwp2tknsrfkzytrm.png)',
        #         '![1024](https://bbs-img-cbc-cn.obs.cn-north-1.myhuaweicloud.com/data/attachment/forum/202010/09/173512tnrpfkysqadqtlee.png)',
        #         '![1024](https://bbs-img-cbc-cn.obs.cn-north-1.myhuaweicloud.com/data/attachment/forum/202010/09/162825q3widemjdlppcjb0.png)',
        #         '![1024](https://bbs-img-cbc-cn.obs.cn-north-1.myhuaweicloud.com/data/attachment/forum/202010/10/111533ab4neej10wtrbmm6.png)',
        #     ])
        # await self.page.type('.textarea', content, {'delay': 30})
        # # await self.page.evaluate('''() =>{ document.querySelector('.textarea').value = '%s'; }''' % content)
        # # await self.page.evaluate('''() =>{ document.querySelector('#mditorBox').value = '%s'; }''' % content)
        # await asyncio.sleep(1)
        # await self.page.click('#fastpostsubmit')
        # await asyncio.sleep(5)

    async def init_user(self):
        page = await self.browser.newPage()

        # await page.setRequestInterception(True)

        async def response_intercept(resp: Response):
            if 'rest/me' in resp.url:
                self.user_id = json.loads(await resp.text())['id']

        async def request_intercept(request: Request):
            url = request.url
            if 'rest/me' in url or 'home/managebonus' in url:
                await request.continue_()
            else:
                await request.abort()

        # page.on('response', response_intercept)
        # page.on('request', request_intercept)
        try:
            await page.goto(self.sign_url, {'waitUntil': 'load'})
            await asyncio.sleep(5)
            await self.close_modal()
            cookies = await page.cookies()
            self.cookies = {}
            for cookie in cookies:
                name = cookie['name']
                value = cookie['value']
                self.cookies[name] = value
                if 'cftk' in name:
                    self.cftk = value
                if 'devclouddevuibjagencyID' in name:
                    self.user_id = value
            return True
        except Exception as e:
            self.logger.error(e)
            return False
        finally:
            await page.close()

    async def get_projects(self):
        page = await self.get_new_win_page(f'{self.domain}/home')
        try:
            await asyncio.sleep(5)
            await page.waitForSelector('.projects-container', {'visible': True})
            items = await page.querySelectorAll('.projects-container .projects-board-in-home a.card')
            self.projects = []
            if items and len(items) > 0:
                for item in items:
                    href = await page.evaluate('item => item.href', item)
                    name = await item.Jeval('div.name', 'e => e.textContent')
                    project_id = str(href).split('/')[-2]
                    self.projects.append({'name': name, 'project_id': project_id})
        except Exception as e:
            self.logger.error(e)
        finally:
            await page.close()

    async def set_default_address(self):
        if self.user_id and self.cftk:
            api = 'https://devcloud.huaweicloud.com'
            cookie_string = "; ".join([str(x) + "=" + str(y) for x, y in self.cookies.items()])
            headers = {
                'x-requested-with': 'XMLHttpRequest',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.54 Safari/537.36',
                'Referer': f'{api}/bonususer/home/managebonus',
                'Cookie': cookie_string,
                'cftk': self.cftk,
                'AgencyId': self.user_id
            }
            session = requests.session()
            response = session.get(f'{api}/bonususer/v2/address/queryPageList?page_no=1&page_size=10',
                                   headers=headers, allow_redirects=False)
            address_data = response.json()
            if 'result' in address_data:
                for item in address_data['result']['result']:
                    address_id = item['id']
                    self.logger.info(item)
                    if int(item['is_default']) == 1:
                        if '校友创新中心' not in item['address']:
                            data = {
                                'address': "校友创新中心3楼壹佰网络",
                                'area': "洪山区",
                                'country': "武汉市",
                                'id': address_id,
                                'is_default': 1,
                                'postal_code': "",
                                'province': "湖北省",
                                'receiver_name': "邹华",
                                'receiver_phone': "18664845253"
                            }
                            response = session.post(f'{api}/bonususer/v2/address/updateAndSetDefault', json=data,
                                                    headers=headers)
                            self.logger.info(f'set default address {response.text}')
                    else:
                        if '国际花园' not in item['address']:
                            response = session.delete(f'{api}/bonususer/v2/address/delete/{address_id}',
                                                      headers=headers)
                            self.logger.info(f'delete address {response.text}')
                    await asyncio.sleep(1)
