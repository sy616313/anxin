const dataset = require('../../data/dataset.js');

Page({
  data: {
    dataVersion: dataset.dataVersion,
    reagentCount: dataset.reagents.length,
    groupCount: dataset.groups.length,
    ruleCount: dataset.rules.length
  }
});
