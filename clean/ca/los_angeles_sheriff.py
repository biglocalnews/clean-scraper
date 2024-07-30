import requests

import json
import os
from pathlib import Path
import time
from typing import List

from .. import utils
from ..cache import Cache


class Site:
    name = "Los Angeles Sheriff's Department"

    def __init__(self, data_dir=utils.CLEAN_DATA_DIR, cache_dir=utils.CLEAN_CACHE_DIR):
        self.siteslug = "ca_los_angeles_sheriff"
        self.rooturl = "https://lasdsb1421.powerappsportals.us"
        self.filestoignore = [
            "index",
            "timestamplog",
            self.siteslug,
            "caseindex"
        ]     # What cached JSON files aren't page-level JSONs?
        self.base_url = "https://lasd.org/"
        self.disclosure_url = (
            f"https://lasdsb1421.powerappsportals.us/"
        )
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)
        self.subpages_dir = cache_dir / (self.siteslug + "/subpages")
        for localdir in [self.cache_dir, self.data_dir, self.subpages_dir]:
            utils.create_directory(localdir)


    def scrape_meta(self, throttle: int = 0) -> Path:
        rawindex = _fetch_index(self)
        oldtimestamps = _fetch_old_timestamps(self)
        indextimes = _build_timestamps(oldtimestamps)
        detailtodo = _build_detail_todo(self, indextimes, oldtimestamps)
        _fetch_detail_pages(self, detailtodo, throttle)
        _save_timestamps(self, indextimes)
        caseindex = _build_caseindex(self, rawindex)
        assetlist = _build_assetlist(self, caseindex)
        assetlist_filename = _save_assetlist(self, assetlist)
        return(assetlist_filename)

    
    def _fetch_index(self):
        rooturl = "https://lasdsb1421.powerappsportals.us"
        indexjsonurl = 'https://lasdsb1421.powerappsportals.us/_services/entity-grid-data.json/f46b70cc-580b-4f1a-87c3-41deb48eb90d'
        indexrequestheaders = {
            "__requestverificationtoken": "kV60zFyBJ_k-mjeiu_6NIKgUlvNWfcwZ9_D29bWM84LeQ5-hNWPjAvr1VVehyAmYc2Cyp9edrQaHD-AKr4duQQPWGxPKvb0mCDZIXIY68NM1",
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json; charset=UTF-8",
            "cookie": "Dynamics365PortalAnalytics=WfAhGy4JV13-E0dhKke0kztJdjYVyjtsY_vFGiSDZAN-KN83-o4lKIwHCj6Rgfuge-xA4zygTbU6OSjgoo1yp5Kw_JU9nd9NHo4FJPYh3DgEYMm16_293HSPMmfYEaGcT7Cw0h4zw3dIqO8J0A3xPw2; ASP.NET_SessionId=djn0vjtl3u2sagzyduk23cab; ARRAffinity=254b55dea5200c22439ddc2bd303a9f6d5189518bb2c795f872095b53e417c82; ARRAffinitySameSite=254b55dea5200c22439ddc2bd303a9f6d5189518bb2c795f872095b53e417c82; timezoneoffset=240; isDSTSupport=true; isDSTObserved=true; ContextLanguageCode=en-US; __RequestVerificationToken=PXUpizhW17-bet0Sh6T6F_W58jnEZDYJXOqylnNVXsykXoWqoLgcYYn2BWOhWpmBhbHqNJJbPujincEmcn0ZBHak6MOK0CifmoNBtxE5ofY1; timeZoneCode=35",
            "origin": "https://lasdsb1421.powerappsportals.us",
            "priority": "u=1, i",
            "referer": "https://lasdsb1421.powerappsportals.us/dis/",
            "request-id": "|5c4f7bc1c8ca42d9901887a721e67944.46457b1429534d7b",
            'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'traceparent': '00-5c4f7bc1c8ca42d9901887a721e67944-46457b1429534d7b-01',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest',
        }
        indexpayload ='{"base64SecureConfiguration":"YLOGHDpWv9SSegnvUu8Q6xsuhm4sBbIIZGj9O4SjcMQWPv+xkcX2MDZ0eR3MbVhJS+9IhnoEBhekXU7nGttQcP6LC5JdGGK1XF3Ur9cD6R+iICx/fjti+6f45B2/nrik5aTComgnLt6NU4J+SMS5yttyFPSYzcJT9DoXMl+I/VdVTaHTx8d1Bu9DWRzAafQ1Ces/zjGq/Rx519F7oDFaNDYhRmZy3Rh3ptAqlM1XwGUosekarbbL4+o1GE9vXWVcc6yNErUbxCuHXqhwIKCB7rYRXDIcI96ZeouJ31bxGpa+sOPFZp4bo6k4WYpMYriki/yHhJ075xL2NdnXZegPdw0DwyIILRRq1uc7oJELvNzOrRfGIaoWRRG4hb0f0tZ6EfOCEVyiztRsDcZl9tSH/gQbS1TdVVI0nEzSQFrTDxFrhj0z87hneGvlra+OnvQPxCjVtiaCpvoZBD2H2bIrbRxMFDhmV3DFOZwgPQlSbQX0jZ5d73A2E5bHiIKYjJ6xxdRt0q5c5jU86wV2OWwN8XjZvXKtP4M6CSJjxlGkxFDIPIePNzI64ZPSO2STc+WB+iLNKYDHuxR240ZSSB8KXFttN3kEKMci04V87eW9vSsUqgjGwdzSSSWRJjRaShmvq3z0k5nXp+Hs5LXm5bf0BfHHKvvfR6G5Q+ZjFk1opjukOWnIeb/FxLabxJSguIrTxGepKBV2zlbL/DhNvic2XtD4cSRNfI83zWNkmzrwxSW7QZe26Ti2St+7ZG2HyuZDdFXcVkzTTA6JoFzSdtBbWcY4uLA8bFoD7oxfsn76G2RrXSX9W0T1zJVUUhtTQcmp5/ynUMXTm2LIO7qWqOG2mlr3dGiBZu9Pp09PmFqXZsiLp6QCBjNZTqTXXykZNNe5/x7sEh8NrUQ1nUcMNhK2u4PvzLFxOv1yqnKIW6tqlGVj19AO51aOBJmB8OyzcJ7BVML6GhSH1viSUstBrHMJ4ne8BcEbWvQv+BQKd2CLOcA6qPIIIpe90ozSDQqAqfHoxGQkBXkndNq09KUkeBJzv6rxEXGiK9HCstmx9Jma52R630kHbR4kaIqtZC+cHTBkl4IIZs/4xd+BmrfB2FyaLfa6RUg163pObnu71qxnpoCMAXM7OqDaHU0iKaAkXk+sXQOWuetbwwwdKeBvT/7tn0bjWxKUn5ltA8w+W7N3aMYy/QYqxQGxbU6VCDr9LXOfW7y8Gt3avvjXmgBmwtmHFor0WEBxOoa+w25lx27F4lqctDUHzU+Lsel9rDT6AMVtV31EGbJ4XRJAiFKG5warxpUOYnCBFfGUj2zDVAkmgeDYLsZFRiVbVqXcLGyDU0Wa4/pTztBGv3egakcP1HMt6zQcsWIK5ZrBeSlLensyIbBPHYl4bFNuDuszTX5OGRZyTEs/kjQuTaOBkhPsAAHLU7jp9gO2WIUTgs6GAs9oLR2+pT79Kgg2hl45aS9tocPDFm4qsWJwoWGJELQav1PTy7MCbHY7Ug7GB5GNKNbA04PTHr3tW+ksQB6EFteZzqrJNeGO6lTWGqzxNZZLOH2Z/91UOJZ9x+Sr+8Bd6+FZnzahvQ5y6rbWVdtrwf06RaItegA2VwuEgHTyG3YSJ4ARE+ICjsn8FlbOpr7MNCPtRKzG92UHorC+dU+2Uglc4QUPmHxAKyu36/8zxv+Q4qyWn4WgkqwFko+4eWWgWaXX30bfwn0cmumEHbWN0znQLIkEKak66wr83/ya37RfAaV+DyrAy5uKsD8cO50MuwYO1czqbaxONbPFuXNqm/9oOdIoJpMwOYCITjOP3ifgG/s+BuKD8G/PSSE7e0bDr4reM/oFD8dnLVSlJPxn8u4QQu9eOOvJCPiucgAA1/ZGWiELwixBMziR5eSJotSVlc21rmGRsN74FJ7d0+wPCz4TosYOtv0EEYGHqb1ImqMkKG4BReM8+V/YcF+LEVNVOvtx3u76Bt/8FJJQfdg7EwwAYITC1JFRnz2gNmJKAlSZN7S70APDEehW+BnZjSp2WxqCFFMrFnjbriQmRUNtF5YFuBAK2NNlwNW3277D5afMhj/a9I3mIGrQ9kG/fAwAXWJRvuGKvZtck+/6JBrMO1wnRVG/ZsWAvpPc4nuaXkf5Mc0mgo9+0GhSV1y0BYlqUPkcu1mreZOsXYT49dFisuygWg3o6MCOBUiPviobeMUJS8oZ6SnUFZgffcVZ58P3r42wUF+yiocEYpSCcCgoGQYCXwwGz0uL8wf4+gFtvMuHMJAiKOAmCwhNTWJNImmGdHVXw7F4eFzHcj41gDl5f9ALgL0UMH/FcxM6zWdxEmAAri0tm0m66X++66y7IWhOlaZKGCE9U5HrZPJx2ig72/IN4cW5mWew9h7lvNaFGSWCDdIEP/4LhZYWOUHoE5ue4mhq7Nc6kE2vQ60ujBhWdF2y4x84q36MFb2N3QY9rRsEIroBSKSRFF0RgzI6JdvJKz7sIQSsU/8IKsIOZzTjWu4WrVaFgZISpTLTpFveOszAzYH+ieI/6coxy/3F+/ZJhidF6ev2+QSo9/DT8FyvP4Ra42Pj4xcOuDVQb1Ib6aJZsNOq+brmZ4MKyXlanPjo8RFgpfgm3A2M1/5ehNL1PpEWu+YBPwEvkqE4l0EJcdRB8cHIT5NynsQ3jcTifphXYwO0wAAvOEEGDXQdeKwg0B6CquM2jrk0jnZljfI6fBejXM/Ih+bpcwW7ruW5+iq8dxRw+o+L+XugqpHaeDfpq3vUwnglEqr6KEZdKBSwEsol3fSGSQmn4yku+9Z0Mww54XVksbTqIBq+1kO6byutzgJtmAX938R7xB1wLfIV55RzCIrPY8hpmdnpGFEIYHFdy4sSguK+CSMJRZMJNsiSRDGizMo6G73OVtXChu72SKHRIhaOS+Dwq+Wey/epF81QVuH12s1ihGFZyZmmG2oVsa+HFsa/ke3x9DdrgQDRD1WblOxRHDwPOiqiSoaZDnaYaW7ZEcvvy2hosroZqSOw0NlhHPeWIQPbJpuUK+IAs6l8XIA+u0d4JX2rT6moDqnpTp9Y6fGtFmDMKKVcJIeYli77ihYOLyhS256Y8XqgvL0ERyXld9eI8BRHLjAaNZoL9es091+cp15Uxh2RLJt9Ucs8wJSTu1JfwrXuImSsBqzqnAUAgDERC7hOL0pEEtpcc0Q51BfGcpzgyR91TVg6jZHTFXvrEfFhBt+h4McoXWV8E7dkOoBy6eCnLGbaiTib989SyJqZ/tFdovPGlBKKIx6ZGVlXcGhgrVwKOy5Hhu/JHnZhpDrxdS7kLQgMsDFzsCG1qhBJkAdyW7FY+uKFkh+algVYNVZRX2JiBXadKQqtzwBAjDovMuvaMAzjIJqPQdzTD+Qs3XG0HryCRqsnYs1zsauAa/4SATwrciWF8Dzd7uTti7BXVjH6LrYR4l3dlJXcVDgmeVB/kKtmvgQuostaZpDXftIhQR35ue0+awtFa+y11NYiEuMPFfquPYF18Emcv0GSoeXeVRvCCF2VtecBH9cHYU/eFFqL+4p1lkOy9i3IrdbMOr1jlt2zJ86W1BVAXWJXeWx5p6ukTmLOBr7USDCnpVUmjGyIhEbXlF8yMDpSCGsOc9qR7ly+EhAJ+hY+90hJqRT7+85YmVLsOAm269c9S/9zM3UE55NXP7wHcQsryYqo4+eejPYOtnFpTeftLGssPm32BvZPn47it8Q+Pl4bzLcF71Tlma1L5lO2i7oXbZENCvIoSpNGQw1SbNLaiW3iJ46zbjKcPIQv/6s2/HUCfLSEAWtHBrdf7cLopgaxTwa9+v0CcVc+1HzPNrd+mZApapNMvsCFlbN/mbhjVGmEr9Ta8gri2nKC2RE1oeZSbN4VMlG+RTVD2ADWh1VkZfbz4whYJ43Yev0jsl7L3A7VQBljmrLUqd5J1w/eIeDamM2RZQy83Yd4+DRF33OTELNEiAvgCa8u7ZQgFjkyekcf0Tua+448kFNr73PcuC9BzUL9zlTwaSvOaIoPzlpo8w9RQYgXEZ5aA4qVBWviyEU3O5QOpLjE4jO+2Dg1depHFmJwVcizaqu+aEGJasQ2JQqOELGMWx+47lNuaYXCBM6HAA6U3AXjUlJYvmhGC7m5BbdcbSsvNOTh4jsE2freh6W1jBs+ymFfkno1Hdvrg6NTGHitW6Zl6Rqg74UzdmQ2QefiTXryoFVVCjfx6auGZhBt9T6uzqr0cglDO9vqug0waCr4dxJSFD16fI9s381ycE2JQ/FqxBlMQcgwFHt84y7GgcUQqWp3GT91eJ7NPuaNpuZ4eRmiilJfZd1l9uBa1rGDLxVOfTXDW1xPDqORlRNNBrpJrsyQ4bELfHPxvCFBVwGjIBoqa2tL+ezlJpd5a/den7KjDnYNmmW/4sleIbo1CAZBAd0x7Q6M4g8220HD66nUG3DATRb3RQqG5O7AgZ4Ll93wS4Wkxat3yBUFRdAFjmqmh5drATkjaAGc9XcCl70jN/gGFujYp0C3ex1iEQ/xmpaNMFG0AkQPYlvHpzDdnw4PIdYY4CQLs9JYrZkTjyviOdT/mKWx20/F/koFFT3ywYPxfXwjqr0zlUfFV6Ynmhe+1Yjck7/Pcje4WXT1NV3FDogEOJ+yNiH3QJM2EG9qQ+l34YjwSGH5m6q9yy/86J82m1u+ZTy6B2acrHnGJCQBNgIGtmbetPAt5bf5Dfj8nM7C3R9yc8qFBmejiRkgkD7JhxLJ/RzqmbSnttgtw2kPBM0amvqmfygs3dnCf2CyrIsbrZHnvHX5vQGBInUBscpDGOmAgetg4/3/h6WgctrXkK/pQwjJCWoS9mOPYTpzQJi9JPYrCDM6gTTfLlp3qmiTetshvjirojLf65MJ48KXttjvmzLGd98/FcPz8XwDg/uejE8mcQDifvq6DAKTd6cT67ZDeXYcOAoRmIWmvUAkS9GEHBiZ4g969huObXmK5mUrP7S30qgRYpHVqfWUul+wsyxReUV2QyFSxs1M6SSd8xnhIncJtZW9/sKbLGYG4RqLDS1vwI9vSOREfOmrwDaqdSjp2UTv/hDloWIXnQdw0HGJRkjsVkKmTKY9q8x6lizl66B4gk/2Onj5g7H9nk/R86/pBMmAMzO7SThWcYOi7Mks5Yd3QHTwm7AYOIa3HMEj2c14r4H0ip8xCU+rAk+dPAo1eaN5yrIosWcyk7N8J+CHWdyR4feNo/R/sMxH2kMRH17DNkW8GaHozNgwyYZiHxQhD4STMPZOjN0JXxz3LVnfSLCB1vsw+lkbJ3stirRikYixMN3lEj2d1ZazkNMsyvAst8Bi9MhfAeh6RwG81QhNYFQYZMJLFtsCNkRWSFSCMdHWsjAVVesnawOaeO18va66PL1hQRceDfS8TY7GesfGAUiiDsiLA6CupudDVLb3+KJWOH6SPLxKscRcyrWe7/kklV01MkOiKMPU0oqd/jSaYfreCvspCjlNgHLhNk5bbQvqjBsJaWK10LqpAy9n3pzlNH6AYzVSyxXKvgThx4rBOrcG6A76hH483JOcY19ECi9GzltakSvztjX4MecdEuggHOU0tXa/g03G++mkd7QQA7+8/zcbGGR2F0DSf8PNc6J9blYJ/GGYiqapYRetjKAe9U2bbGQiiaD8lgZqcyHlRi+mtXBMRNXgG0fBgSsIstl0P5nKtHRaaE+WezGgBxslZRXiZ8MOgFka5qDbXQ2Tvd2ZQ/B5Aop0Y1cc44JRoOLyyVGPxysxSfaReqVymIN9x3l9oRKUKripSIMmPLNp5BHQv45jU5f4O6wRJkxnRpHZ6llSVWrc+hVLPD98v7XTPQxmaP33JtbKZeXQ77KGH5FeSh7ykg9rRNeSYBuIUgXScg8YPNtQCKkuI+Kfg2Vb34/AI5Tato6nvQpRGzUjNrpiY3Dw0oL+bLhmtU4Va5VJ8Nv1NIuI47hxv8JD0hlPWfLU/TpWhrtEyXtHGXLjDosSPLIxwxq5cCldJY9Vwe9C6EynfI7e+q/nwnNmVRXiOxYB8rKoxb2CcJajbDZ9OLL+xQSWDznqlmxrJ7FEgAvfUSp9DXuBpa7aoeFO3hQGPZeFlE2G1As2L+5zY0ZCMkATQQJwd9dz05zVH87Az7iBCHpcFVP7zKtnXhIh5EIQX3iQydsKz7y6rXGCm2q1nOjz/42K3/XD72DUU3L4U5E48tZVZHQpNOa94o29JpD2Dk2gRq/aEDjh/i7JMasjnofQL9Nx1hnj3ufA/u+mBBuAPcv10THbgXmnVm7RBPtBJwyI9QsT/PWcRkG/u7i4EbaCmGWZOF1/wL0jz7CephcRxsG+3PopNtGXfJ+/F/Hac6Y8ZXE6gNJs167u1vkbzPtK1WGZ8WLRVF/GoYNsfZNvyjnzeBc1XAcG1+jXuN1tyR3EVh9xf3WAEhLvy/Ugjd3cBdQ77LxhqQizAUtE4xszP1XpjpVjajlSU8IwPUEwj5jMpPtTCcsnIGdIwsd456TnNYKBW5XHySvbl9wZGQjKJiIHsi5aO47X+WvkU2fZLFmv/V1wizba89rmIr436IEHCV6UUKfBq0z2/I9apJM0eaXcdxp+pWwhIsHdpeXah6us83h6/ijXoZvLvSQM56vzcrPueogj+3eEzmCARMxln9gXAHSgLXYyRCIpg40sQRH/FqqJajqCy2RoOxoOiZPO79rN0yCWl9NTAPQ3usi4FuNduqfZTIp7FSJgtcBO8+iKoHwujbFdoRJ6jV+jt86CZ+nfknMzZdaxIKEPszQm2eP56Ti3IiY0VhfzAqbj/PhVtjsBJIi7zEv3jcJpspihDwEXz8mNxMTMaJ/TNjVibIkz4VvZjpD6ztbh78kgaycioWrSbWhFepxoRZA30IEeYILYdQUx0/vmBxghPPXEBIhrkwR7f3OmkXmOY6elZrx7HJfqBDlsAGPyxtpfAJ7l08HtnX1UI2LtZ1qciJo6yK1pWFgjjl+fHoyB2D+2fNLf7K+Q51HpbTpgJh/9LmxnSTgcCFcyibeAhbYBmV9z+ZbmdwO0tYdXHyGzke8bMN1C2fWdmz8wsoZS9wCMHzscGU2+M8eQbcH0pcU6HDKVXaydOz+lcROpChEbmXgq1xL7YZOXSDiMxxBsYfrT7ZJZFa1KSY+caSr1+saVVjjepZzzXtgnxGy5OdJqiPAJvE6ZLxjU4oAv9JTVLo9Oy/Lpn9iaiIi+mPT2DLNhOXW2LuKkH98xVTbgPo9B8CHe3TaFVu0xfz6mDRYZ0zWDfUB/GkdXBSgH5BsDoKWSFQ4kShgIogWthCVd9Q76S5JDXLWFHHK7A2/JSuUwMsQVDEFM7ly1/rcleLIFbICInfGMBTDXciv8o32tuo/sl3xSU2fkTlzkzy0e/+2wSINx5SPE2rWDMjyLKsCoWqzSWc5jqvFi/2PZQudoSixd5aTbYTNicNwpWiFgEJMjRqw0Gm33565ThYPQVlCuM3ln1MV+5j5cmu7DWKNhkoBhaYwmZyOijTYswFiXYgoWSkVyBKVArENUTlsMA8Uqt2UTXxhpAUXEltZPyNNBiFSgnBlD9epz1exQPA7Z3wPa1hnkswznH73jIxnGndZoSTXOasNiQFw70NNRZjt5cMkgPQ9croVA6F2J7EYZMl7wQ3O+bZYpOBQIHDxZW/iJYSdPMzrTltj+DmGG34/lDL94aVBYoKcAw44LUMO4FYM5JJsYSFGmoXAlcP4tAYuE9ad7ExdkuePMM6777DjT/CCOL8B+lIL8qdnlhoTPUlzxHeJlVisz8aAo96YB47HmAhYngk1l21fyqHp7/qY8Lp0yMFJ6KQ2H7hENWkVc1oulGNoI0mZ2SM9NsyFzO9svBqy8TbK7Is7+aIvcACp5hcr7eRgk2ipl03OovatbYj7JByRLw5AKuCq1/pL9l9gzU0cabSbvSxHkUo2eGqK+zUdm5me+FHZW8WIVbfvSG3zchiEYUBx3HBKGBfBgbSK5sGeF7Awm7yvmuHMt9eW3YCPJdaKZGM+fGEVA8TF4IUtV8HIqBb97cjFi5cGWZKmznI27OaeiiB1d4Gck/46s676DL6YfHJUIRuCjXdaLvnrqpbc73lsskVomEJBcsm697l4JK7WNRzeRmzkV+iZhvM/w2iQZCJy7zkEthcKnW+Dok2YOLFEe5PVlCC9aMhjBAEejl8slLXN0Fyo4z0REDSNmPkXlpgB+XPhoSlTL4c9P0cp7jvSYGHdHJ/4PCEbBGCVzjbG3+dpumh0dxttgw32HZxIxj2gxvODoF5hxE38bvOSuiBWtVF2fyIDoDcVRQkTEY8xYBEerw2CjTVvgx0Cbrzq6Mn68rzG2iYCd6RbUe4sf6tClAiPwwShGLibIv5dYORz2eYpVkejEOo0HI5o8Kn18B0Fg29MITmRvvQoCAqPVylM2ezt7xd/zlgt0UXk54gUUvcWEfhg5sf1Z6myAYaPOdvMsPg7qCmU5elaC3dTj4TKtXQit+7kQk9DCMkvS7CGW5ojuyVIyDuY479mqcdzpsWeljfPG/4InENDnCQhOU+kITPDYFToTON7UawTdCcSPkRjXzzq+CyQ5kzKC8NFzyQcHfMbYF8Bal7fxCZ6prnclrxpiMu3IGffG4+J3gQwmH+/VD8QK87UBYTgWuOUBNx4o7j4Fc5Ovg3GJiDkoYQBEQhIMSZnb0+MSbciCTUWCIQfS9d/+O6EKdJCzBD62iBVQOpQlF10gsrAi8jRB65ML5zqjFM8Hm3ruMBFUHoy8mrluJZlyn5h3PNV+4/4e0CFZunQhcqUbagecl54Av1SV9QW3+Yg9dkZ1Un77sGJe4HP7xdPCK7UAokJ/bog7VHUmPHo8GuDDcPErv7JTk1mIFIedjWVyGWOTSeHRp/Xv9OZX/sOaPGRiMDt8Ph3KicAbMEC60RN4IKa0nivG7I/yLxgw5ZpWiVaDO0KJJPjtiobKGhx0a5eAO6IV5BDSXF88A0otjGwDxwWXMoP3N5Nvjld9IueUKxxUTi1VBNGsw4UpNkr9+uSDcix4kFaHGqAwX2xmN3JnQ21CA91BWQssSQAqQua8JxdHUbwtnbXmiMa3dR9trjnjLXaezZlDuredqOT6LuWHtt0RCVX/htJ2Ro3CPilAcX+fl3lYxFNpxlbGQiJyFTJeolnwUOzglOXJW9EFvYpXtL8TsBoEJevMKcu3sUVShAJG4PnsKJzHRAjT7Mnv3vpSC4vrlG3N0J9v7rpst4No7cNWF9M0jswvk3ZXn6MuNAhfMHdAX7qLqGVbjhypmXggRgf5heN8Y5paFvY8Grmx+BuvCYvq6NCplVjmTo55LqZ78hoHr3ECqkwblmnAHhoMBuUW/mJajvF+Qrfn11++i7hbYizLdUSaReRECmmEllEfY/IHa6NgLMFIPEnTkMEiTXHf7kdYvZuwckiprpFDpenks/D5QBI2Y+DhFM5W7YVGFtwYj22LfRoJ7Eyxd6bHByVjU0MwkyO15FpKLtoU359Nc/EkLIF3fIWMH+/JBMhNtq8GKPqPiIa8RsbLKKpykOXJ/9qvhvm4Mbj/UJJP/5YLP/lBGmYz/kt26dp5r06pRe0K/7SNe1Ow1TCah/mpA74VnA4cr9blZW0F4T/WPC2fc/C1rLWqNQgrR9mUR4LRQGYnwApxItjx3AGHv02RXIFzwBPo5o1+jS0Qmb9tE/7pQTWPbCQTeL06JFwrFmdZwLKBwFUl5f79KDmtOecyYj6W8CHp93rzkCBWyfKLXC4IuEO7zsdipIK6J/i1w9RjiTiea3+Lz3UsUei/C2AglkeZ3KQsiC91QFTeHnUkmoelVMAcsbCpKIot6RHwKISNil0bi8v5XetzQzRRM5KMKxa0A2ORHrvXe74RpliKEwRCncrXsfpwQiHxOzkGFRdcPOPQhX2FdxLHVLhEGDMNDFEfRMAEKZIUGAnpCg/c//bgiFSNX4mrkXaCkuBYqbkeLIx2E23M0dEdDJYAyzSgYlrmSQGyBbRxpyi0ubGeK04zsLnCEa1QqseYjgigz/m/yRAj+rduX1GzJKiaF1SE+oc/iGp9kWe7Yv67fC8TfKxNQ1XPo+hOvkAkfrbPUWmp90mL9Le638Olnks7/gkhvWu+aho2YRxaoW14zLfQ6JGlyWVKt+rESoDefNmWM7S0zj8NPwVmciv/J39ruk8tIxo42KyaFiC0C0Z/NWA/mnCF7ZyTvLFCAoJegawjczO1+mjym+gOXqLL6wTXsavxiv7DlyvEqqIe9FNixON7ZET7RUkprkTQ05UGV14SCNSpkwXAuWa70a29YDxo7wEEbCnHLh8vSN1l/ArQPiMxtv16dnfJfkMSncXGybQK/jIJ8YWtOqq8PYV7QYXNB22oV0AbASd+aa3J51gYdXxOYvXOsugo3YgmUTZYBOshQpbOA1AIoGpnGNr/x2QAfoZOCJe2QNlsvUY53M6sNoJwrppKOG4QlXEYIFYPFeZ9UvcyMmGzNoILLentNk1rGftcPJl53tgy9LNrl+KKkZuTDAyGMef7rZXBfrx3d/HduAw45fLOKBCTRRCtIc70IBQxey3vPWFWM2MoWm6UmWDWYS+2K9zInzj87a8p35J76K7wgDKkQ28T6Lcisw39krzq/X72qWPmb1BlawoTV3/wHCduwsDs2RhLKiZ7U7j8AM6rArawvZ2e0fb715DUe94=","sortExpression":"sb1421_eventdate ASC","search":"","page":1,"pageSize":9999,"pagingCookie":"","filter":null,"metaFilter":null,"timezoneOffset":240,"customParameters":[]}'    
        r = requests.post(indexjsonurl, headers=indexrequestheaders, data=indexpayload)
        with open(self.cache_dir / (self.siteslug + "/index.json"), "wb") as outfile:
            outfile.write(r.content)
        with open("index.json", "r", encoding="utf-8") as infile:
            rawindex = json.load(infile)
        if rawindex['MoreRecords'] or len(rawindex['Records']) != rawindex['ItemCount']:
            print(f"Index JSON is incomplete or broken.")
        else:
            print(f"{rawindex['ItemCount']:,} records found.")
        return(rawindex)


    def _build_timestamps(indexjson: dict):
        indextimes = {}
        for record in rawindex['Records']:
            recordid = record['Id']
            timestamp = ""
            for entry in record['Attributes']:
                timestamp += entry['AttributeMetadata']['ModifiedOn']
            indextimes[recordid] = timestamp
        return(indextimes)


    def _fetch_old_timestamps(self):
        filename = self.cache_dir / (self.siteslug + "/timestamplog.json")
        if site.cache.exists(filename):
            with open(filename, "r", encoding="utf-8") as infile:
                oldtimestamps = json.load(infile)
        else:
            oldtimestamps = {}
        return(oldtimestamps)


    def _save_timestamps(self, indextimestamps):
        filename = self.cache_dir / (self.siteslug + "/timestamplog.json")    
        with open(filename, "w", encoding="utf-8") as outfile:
            outfile.write(json.dumps(indextimestamps))
        return


    def _get_detail_json(self, recordid: str):
        detailrequestheaders = { 
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json",
            "__RequestVerificationToken": "eHcTqQbCi1LqT2xhe50AZS-IY_4JPB6S-WOyeZ_43BorhlZfHO77Q69jKWO3bctuMtKNHSjY_SxQmKCmC0G2N8vhr-3KKu8cOa4GJ15NgOE1",
            "X-Requested-With": "XMLHttpRequest",
            "Request-Id": "^|180fc898383b4cdea9562818e9ccb2f0.6971a699587e4f02",
            "traceparent": "00-180fc898383b4cdea9562818e9ccb2f0-6971a699587e4f02-01",
            "Origin": "https://lasdsb1421.powerappsportals.us",
            "Connection": "keep-alive",
            "Referer": "https://lasdsb1421.powerappsportals.us/disfiles/?id=13434aab-ab8b-ed11-81ad-001dd830a125",
            "Cookie": "Dynamics365PortalAnalytics=I96I2Tvt4N-gPaURejqoFAgdfpCOkV7mfdXsXEgZZq8CooQCFX8ewO5C6tTxgHKGjV8Nqh30acufK6AFfDtdV_SivR7HLAZg5f476jxkzB394E5aPLo8PDI_xXsBmLWgXb5Sf28dZJ2CxuI4re7ZEA2; ASP.NET_SessionId=2k2vrqpb53tklzcqz0ftqqyy; ARRAffinity=254b55dea5200c22439ddc2bd303a9f6d5189518bb2c795f872095b53e417c82; ARRAffinitySameSite=254b55dea5200c22439ddc2bd303a9f6d5189518bb2c795f872095b53e417c82; timezoneoffset=240; isDSTSupport=true; isDSTObserved=true; ContextLanguageCode=en-US; timeZoneCode=35; __RequestVerificationToken=Y4mVGr7Dq1OfgQav9ztK4nDJNNtdU450gGRn6puub7-qbXeiwIiFBzyn-ZFIiwLgFTh13dMhEtTlTXdIUiXIlVaAKO9XENzlm-qMbNC5Egg1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "TE": "trailers",
            }
        detailpayload = '{"regarding":{"Id":"IDGOESHERE","LogicalName":"sb1421_sb1421responsiverecords","Name":null,"KeyAttributes":[],"RowVersion":null},"sortExpression":"FileLeafRef ASC","page":1,"pageSize":9990,"folderPath":""}'
        referer = "https://lasdsb1421.powerappsportals.us/disfiles/?id=" + recordid
        detailrequestheaders['Referer'] = referer
        localpayload = detailpayload
        localpayload = detailpayload.replace("IDGOESHERE", recordid)
        targeturl = "https://lasdsb1421.powerappsportals.us/_services/sharepoint-data.json/" + recordid
        targetfilename = self.subpages_dir / (recordid + ".json")
        r = requests.post(targeturl, headers=detailrequestheaders, data=localpayload)
        if not r.ok:
            print(f"Problem downloading detail JSON for {recordid}")
        else:
            with open(targetfilename, "wb") as outfile:
                outfile.write(r.content)


    def _build_detail_file_list(self):
        cachefiles = site.cache.files(subdir=self.siteslug + "/subpages")
        recordsdownloaded = set()
        for cachefile in cachefiles:
            corefilename = cachefile.replace("\\", "/").split("/")[-1].replace(".json", "")
            if corefilename not in self.filestoignore:
                recordsdownloaded.add(corefilename)
        return(recordsdownloaded)


    def _build_detail_todo(self, indextimes, oldtimestamps):
        todo = set()
        recordsdownloaded = _build_detail_file_list(self)    
        for recordid in indextimes:
            if recordid not in recordsdownloaded:
                todo.add(recordid)    
            elif recordid not in oldtimestamps:
                todo.add(recordid)
            elif indextimes[recordid] != oldtimestamps[recordid]:    # If something got modified, maybe
                    todo.add(recordid)
        print(f"{len(todo):,} subpages to download")
        return(todo)


    def _fetch_detail_pages(self, detailtodo, throttle):
        for recordid in detailtodo:
            _get_detail_json(self, recordid)
            time.sleep(throttle)


    def _build_caseindex(self, rawindex):
        caseindex = {}
        sectiontypes = ["case_number", "recordid", "case_type", "suspectvictim", "event_date_epoch", "event_date_human", "release_date_epoch", "release_date_human"]
        for record in rawindex['Records']:
            line = {}
            for sectiontype in sectiontypes:
                line[sectiontype] = None
            line['recordid'] = record['Id']
            for a in record['Attributes']:
                if a['Name'] == "sb1421_name":
                    line["case_number"] = a['Value']
                elif a['Name'] == 'sb1421_caseorincidenttype':
                    line['case_type'] = a['DisplayValue']
                elif a['Name'] == 'sb1421_suspectvictim':
                    line['suspectvictim'] = a['Value']
                elif a['Name'] == 'sb1421_publicreleasedate':
                    line['release_date_human'] = a['DisplayValue']
                    line['release_date_epoch'] = int(a['Value'].split('(')[1].split(')')[0])
                elif a['Name'] == 'sb1421_eventdate':
                    line['event_date_human'] = a['DisplayValue']
                    line['event_date_epoch'] = int(a['Value'].split('(')[1].split(')')[0])
            caseindex[line['recordid']] = line
        return caseindex


    def _build_assetlist(self, caseindex):
        assetlist = []
        recordsdownloaded = _build_detail_file_list(self)
        for recordid in recordsdownloaded:
            sourcefile = self.subpages_dir / (recordid + ".json")
            with open(sourcefile, "r", encoding="utf-8") as infile:
                localjson = json.load(infile)
            for asset in localjson['SharePointItems']:
                line = {}
                line['asset_url'] = self.rooturl + asset['Url']
                line['name'] = asset['Name']
                line['parent_page'] = str(sourcefile).replace("\\", "/").split("/")[-1]
                line['title'] = asset['Name']
                line['case_num'] = caseindex[recordid]['case_number']
                line['file_size'] = asset['FileSize']
                line['details'] = {}
                line['details']['date_modified'] =  asset['ModifiedOnDisplay']
                line['details']['date_created'] = asset['CreatedOnDisplay']
                for item in ["case_type",
                             "suspectvictim",s
                             "event_date_epoch",
                             "event_date_human",
                             "release_date_epoch",
                             "release_date_human"
                            ]:
                    line['details'][item] = caseindex[recordid][item]
                assetlist.append(line)
        return(assetlist)


    def _save_assetlist(self, assetlist):
        targetfilename = self.data_dir / (self.siteslug + ".json")
        print(f"Saving asset list to {targetfilename}")
        with open(targetfilename, "w", encoding="utf-8") as outfile:
            outfile.write(json.dumps(caseindex, indent=4*' '))
        return(targetfilename)

    
