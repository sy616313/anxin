const dataset = require('../../data/dataset.js');

Page({
  data: {
    dataVersion: dataset.dataVersion,
    // 四类场景。完整处置流程需经指导教师审核后于 D4（任务书 T4.5）上线，
    // 此处只列出分类，不给可能出错的细节。
    scenes: [
      { key: 'eye', title: '化学品溅入眼睛', note: '首要动作：立即用洗眼器或大量清水持续冲洗，并就医。' },
      { key: 'skin', title: '化学品接触皮肤', note: '首要动作：立即脱去污染衣物，用大量清水冲洗，并就医。' },
      { key: 'fire', title: '实验室着火', note: '首要动作：切断气源电源，就近取用灭火器，同时报警并撤离。' },
      { key: 'spill', title: '化学品泄漏 / 汞洒落', note: '首要动作：疏散无关人员，通风，由安全员处置，勿自行清扫。' }
    ]
  }
});
