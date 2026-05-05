# fupan
fupan
重要！！！必须做好一系列反爬虫反IP处理，以免自己的ip被封！！！
这是一个python爬虫 + akshare 拉复盘数据项目
目前akshare暂时还不用，但是可以先进入进来了
这个项目我打算做一个每天下午6点自动更新的一个ai网页。
目前功能就1个：3日内多日上龙虎榜的个股。
需求：调用最近3个交易日的数据，看下谁多次上了龙虎榜。列个清单，显示下次数。样式你自己定

接口是POST：https://duanxianxia.cn/api/getLhbByStock
参数就1个：date
例子：{
    date:2026-04-30
}
返回例子：[
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化打板买",
                "id": "YZ00054",
                "type": "hot_money"
            },
            {
                "color": "red",
                "name": "方新侠买",
                "id": "YZ00032",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "宁波桑田路卖",
                "id": "YZ00031",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "中国长城",
            "code": "000066",
            "zf": "9.99"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [],
        "info": {
            "name": "金螳螂",
            "code": "002081",
            "zf": "10.07"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "量化基金T",
                "id": "YZ00049",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化打板卖",
                "id": "YZ00054",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "莲花控股",
            "code": "600186",
            "zf": "-0.92"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化基金买",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "寒武纪",
            "code": "688256",
            "zf": "20.00"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "山东帮买",
                "id": "YZ00024",
                "type": "hot_money"
            },
            {
                "color": "orange",
                "name": "T王T",
                "id": "YZ00090",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "博云新材",
            "code": "002297",
            "zf": "5.56"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化打板买",
                "id": "YZ00054",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "T王卖",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "西部材料",
            "code": "002149",
            "zf": "9.99"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "杭州帮买",
                "id": "YZ00009",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "瑞鹤仙卖",
                "id": "YZ00023",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "宝光股份",
            "code": "600379",
            "zf": "10.03"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "理奇智能",
            "code": "301599",
            "zf": "348.60"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化打板买",
                "id": "YZ00054",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "万通发展",
            "code": "600246",
            "zf": "10.05"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "豫能控股",
            "code": "001896",
            "zf": "-9.98"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            }
        ],
        "info": {
            "name": "丰元股份",
            "code": "002805",
            "zf": "10.01"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "越剑智能",
            "code": "603095",
            "zf": "10.02"
        }
    },
    {
        "days": [
            "1",
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "欢乐海岸买",
                "id": "YZ00019",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "融捷股份",
            "code": "002192",
            "zf": "10.00"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "玉兰路买",
                "id": "YZ00038",
                "type": "hot_money"
            },
            {
                "color": "red",
                "name": "低位挖掘买",
                "id": "YZ00076",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "美诺华",
            "code": "603538",
            "zf": "-4.35"
        }
    },
    {
        "days": [
            "1",
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "量化打板买",
                "id": "YZ00054",
                "type": "hot_money"
            },
            {
                "color": "red",
                "name": "中山东路买",
                "id": "YZ00087",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "光莆股份",
            "code": "300632",
            "zf": "20.01"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化打板买",
                "id": "YZ00054",
                "type": "hot_money"
            },
            {
                "color": "red",
                "name": "成都系买",
                "id": "YZ00013",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "创世纪",
            "code": "300083",
            "zf": "20.02"
        }
    },
    {
        "days": [
            "1",
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "orange",
                "name": "量化打板T",
                "id": "YZ00054",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "翔鹭钨业",
            "code": "002842",
            "zf": "10.00"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "量化基金T",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "水发燃气",
            "code": "603318",
            "zf": "-1.99"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化打板买",
                "id": "YZ00054",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "T王卖",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "盛新锂能",
            "code": "002240",
            "zf": "9.99"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "量化基金买",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "舒华体育",
            "code": "605299",
            "zf": "9.99"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "green",
                "name": "T王卖",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "中晶科技",
            "code": "003026",
            "zf": "5.42"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "T王T",
                "id": "YZ00090",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "金开新能",
            "code": "600821",
            "zf": "-10.03"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化基金买",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "维科技术",
            "code": "600152",
            "zf": "2.41"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "T王T",
                "id": "YZ00090",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "山东帮卖",
                "id": "YZ00024",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "众合科技",
            "code": "000925",
            "zf": "-5.84"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "川能动力",
            "code": "000155",
            "zf": "-9.51"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "orange",
                "name": "炒股养家T",
                "id": "YZ00011",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "海德股份",
            "code": "000567",
            "zf": "10.07"
        }
    },
    {
        "days": [
            "1",
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "orange",
                "name": "T王T",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "大普微",
            "code": "301666",
            "zf": "7.43"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化打板卖",
                "id": "YZ00054",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "飞马国际",
            "code": "002210",
            "zf": "-9.97"
        }
    },
    {
        "days": [
            "1",
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "量化基金买",
                "id": "YZ00049",
                "type": "hot_money"
            },
            {
                "color": "orange",
                "name": "量化打板T",
                "id": "YZ00054",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "德方纳米",
            "code": "300769",
            "zf": "12.92"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "瑞鹤仙买",
                "id": "YZ00023",
                "type": "hot_money"
            },
            {
                "color": "orange",
                "name": "量化基金T",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "丽岛新材",
            "code": "603937",
            "zf": "10.03"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "orange",
                "name": "量化基金T",
                "id": "YZ00049",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "温州帮卖",
                "id": "YZ00015",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "长龄液压",
            "code": "605389",
            "zf": "9.84"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "芯原股份",
            "code": "688521",
            "zf": "20.00"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化打板卖",
                "id": "YZ00054",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "卓郎智能",
            "code": "600545",
            "zf": "-9.94"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化基金买",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "宏源药业",
            "code": "301246",
            "zf": "15.76"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "炒股养家买",
                "id": "YZ00011",
                "type": "hot_money"
            },
            {
                "color": "red",
                "name": "量化打板买",
                "id": "YZ00054",
                "type": "hot_money"
            },
            {
                "color": "orange",
                "name": "量化基金T",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "天域生物",
            "code": "603717",
            "zf": "10.07"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化基金买",
                "id": "YZ00049",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "低位挖掘卖",
                "id": "YZ00076",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "华升股份",
            "code": "600156",
            "zf": "-3.31"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "方新侠买",
                "id": "YZ00032",
                "type": "hot_money"
            },
            {
                "color": "orange",
                "name": "量化基金T",
                "id": "YZ00049",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "玉兰路卖",
                "id": "YZ00038",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "盛合晶微",
            "code": "688820",
            "zf": "11.35"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "低位挖掘买",
                "id": "YZ00076",
                "type": "hot_money"
            },
            {
                "color": "red",
                "name": "宁波桑田路买",
                "id": "YZ00031",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "凌云光",
            "code": "688400",
            "zf": "20.01"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "量化基金买",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "共创草坪",
            "code": "605099",
            "zf": "10.00"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化打板买",
                "id": "YZ00054",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "海昌新材",
            "code": "300885",
            "zf": "19.98"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "orange",
                "name": "量化基金T",
                "id": "YZ00049",
                "type": "hot_money"
            },
            {
                "color": "orange",
                "name": "量化打板T",
                "id": "YZ00054",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "金瑞矿业",
            "code": "600714",
            "zf": "10.01"
        }
    },
    {
        "days": [
            "1",
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "徐留胜买",
                "id": "YZ00029",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "日联科技",
            "code": "688531",
            "zf": "20.00"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化打板买",
                "id": "YZ00054",
                "type": "hot_money"
            },
            {
                "color": "orange",
                "name": "量化基金T",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "津投城开",
            "code": "600322",
            "zf": "10.08"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化打板买",
                "id": "YZ00054",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "新赛股份",
            "code": "600540",
            "zf": "10.06"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "淳中科技",
            "code": "603516",
            "zf": "-10.00"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "量化打板买",
                "id": "YZ00054",
                "type": "hot_money"
            },
            {
                "color": "orange",
                "name": "炒股养家T",
                "id": "YZ00011",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "温州帮卖",
                "id": "YZ00015",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "中天精装",
            "code": "002989",
            "zf": "10.02"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "green",
                "name": "T王卖",
                "id": "YZ00090",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "杭州帮卖",
                "id": "YZ00009",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "中科仪",
            "code": "920186",
            "zf": "6.14"
        }
    },
    {
        "days": [
            "1",
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            }
        ],
        "info": {
            "name": "鸿仕达",
            "code": "920125",
            "zf": "29.99"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            },
            {
                "color": "red",
                "name": "量化基金买",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "ST南都",
            "code": "300068",
            "zf": "-19.98"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [],
        "info": {
            "name": "*ST易录",
            "code": "300212",
            "zf": "-20.02"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [],
        "info": {
            "name": "宏英智能",
            "code": "001266",
            "zf": "2.71"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "诚邦股份",
            "code": "603316",
            "zf": "-4.94"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "orange",
                "name": "量化打板T",
                "id": "YZ00054",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "行云科技",
            "code": "300209",
            "zf": "2.58"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "green",
                "name": "歌神卖",
                "id": "YZ00006",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "美之高",
            "code": "920765",
            "zf": "24.73"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "中创智领",
            "code": "601717",
            "zf": "-9.98"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "orange",
                "name": "T王T",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "ST云动",
            "code": "000903",
            "zf": "-3.52"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "温州帮买",
                "id": "YZ00015",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "先惠技术",
            "code": "688155",
            "zf": "20.00"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "orange",
                "name": "T王T",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "*ST正平",
            "code": "603843",
            "zf": "5.04"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "有研复材",
            "code": "688811",
            "zf": "12.05"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "green",
                "name": "T王卖",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "*ST中迪",
            "code": "000609",
            "zf": "5.03"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "花呗哥买",
                "id": "YZ00084",
                "type": "hot_money"
            },
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "欧莱新材",
            "code": "688530",
            "zf": "7.04"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [],
        "info": {
            "name": "太极股份",
            "code": "002368",
            "zf": "-10.02"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "量化基金买",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "ST喜临门",
            "code": "603008",
            "zf": "-4.97"
        }
    },
    {
        "days": [
            "1",
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "一瞬流光卖",
                "id": "YZ00058",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "ST天玑",
            "code": "300245",
            "zf": "-15.43"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "orange",
                "name": "量化基金T",
                "id": "YZ00049",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "低位挖掘卖",
                "id": "YZ00076",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "迅捷兴",
            "code": "688655",
            "zf": "18.60"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "orange",
                "name": "T王T",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "*ST皇庭",
            "code": "000056",
            "zf": "-4.92"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "泰金新能",
            "code": "688813",
            "zf": "6.86"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "green",
                "name": "章盟主卖",
                "id": "YZ00002",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "ST朗进",
            "code": "300594",
            "zf": "-20.02"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "广东帮买",
                "id": "YZ00021",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "ST百利",
            "code": "603959",
            "zf": "-5.01"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "章盟主卖",
                "id": "YZ00002",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "海昌智能",
            "code": "920156",
            "zf": "9.93"
        }
    },
    {
        "days": [
            "1",
            "3",
            "10"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "10日",
                "id": null,
                "type": "range"
            }
        ],
        "info": {
            "name": "卓然股份",
            "code": "688121",
            "zf": "-16.06"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "天宸股份",
            "code": "600620",
            "zf": "-9.95"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "ST棕榈",
            "code": "002431",
            "zf": "-5.02"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [],
        "info": {
            "name": "达意隆",
            "code": "002209",
            "zf": "-9.98"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "成都系买",
                "id": "YZ00013",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "*ST春天",
            "code": "600381",
            "zf": "4.97"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "ST麦趣",
            "code": "002719",
            "zf": "-4.84"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "red",
                "name": "量化基金买",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "精进电动",
            "code": "688280",
            "zf": "-11.86"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            },
            {
                "color": "green",
                "name": "广东帮卖",
                "id": "YZ00021",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "温州帮卖",
                "id": "YZ00015",
                "type": "hot_money"
            },
            {
                "color": "green",
                "name": "量化基金卖",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "*ST亚振",
            "code": "603389",
            "zf": "4.99"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "量化基金买",
                "id": "YZ00049",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "ST清越",
            "code": "688496",
            "zf": "-19.93"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [],
        "info": {
            "name": "族兴新材",
            "code": "920078",
            "zf": "9.13"
        }
    },
    {
        "days": [
            "3"
        ],
        "tags": [
            {
                "color": "orange",
                "name": "3日",
                "id": null,
                "type": "range"
            }
        ],
        "info": {
            "name": "ST信安",
            "code": "688201",
            "zf": "-13.42"
        }
    },
    {
        "days": [
            "1"
        ],
        "tags": [
            {
                "color": "red",
                "name": "T王买",
                "id": "YZ00090",
                "type": "hot_money"
            }
        ],
        "info": {
            "name": "赛英电子",
            "code": "920181",
            "zf": "7.87"
        }
    }
]