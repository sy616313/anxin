// 小程序入口
// 数据由 scripts/sync_data.py 从仓库 data/ 生成到 miniprogram/data/dataset.js，
// 引擎由同一个脚本从 engine/index.js 拷贝到 miniprogram/engine/index.js。
// 改完 data/ 必须跑 python scripts/validate_data.py（它会自动同步）。

const dataset = require('./data/dataset.js');

App({
  globalData: {
    dataset: dataset
  },

  onLaunch: function () {
    console.log('[安芯] 数据版本 ' + dataset.dataVersion +
      '，试剂 ' + dataset.reagents.length +
      ' 条，规则 ' + dataset.rules.length + ' 条');
  }
});
