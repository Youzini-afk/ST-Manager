import assert from 'node:assert/strict';

import {
  computeFloorVariableSnapshot,
  createFloorVariableSnapshotResolver,
} from '../static/js/utils/chatReaderVariableSnapshots.js';

const baseMessages = [
  {
    swipe_id: 1,
    variables: [
      {
        stat_data: {
          人物: {
            名称: '',
            当前生命值: 0,
          },
        },
        source: 'inactive-swipe',
      },
      {
        stat_data: {
          人物: {
            名称: '癌骑士',
            当前生命值: 30,
          },
        },
        source: 'active-swipe',
      },
    ],
  },
  {
    swipe_id: 0,
    variables: [
      {
        stat_data: {
          人物: {
            名称: '癌骑士',
            当前生命值: 15,
          },
        },
        floor_flag: 'floor-2',
      },
    ],
  },
  {
    swipe_id: 0,
    variables: [
      {
        misc: 'kept',
      },
    ],
  },
];

function testComputeSnapshotUsesActiveSwipe() {
  const snapshot = computeFloorVariableSnapshot(baseMessages, 1);
  assert.equal(snapshot.stat_data?.人物?.名称, '癌骑士');
  assert.equal(snapshot.source, 'active-swipe');
}

function testComputeSnapshotAccumulatesUpToFloor() {
  const snapshot = computeFloorVariableSnapshot(baseMessages, 2);
  assert.equal(snapshot.stat_data?.人物?.名称, '癌骑士');
  assert.equal(snapshot.stat_data?.人物?.当前生命值, 15);
  assert.equal(snapshot.floor_flag, 'floor-2');
}

function testResolverCachesWithoutChangingResults() {
  const resolver = createFloorVariableSnapshotResolver({ checkpointInterval: 2, maxRecentSnapshots: 2 });
  const floorTwo = resolver.resolve({
    chatId: 'demo',
    rawMessages: baseMessages,
    floor: 2,
  });
  const floorThree = resolver.resolve({
    chatId: 'demo',
    rawMessages: baseMessages,
    floor: 3,
  });
  const floorOne = resolver.resolve({
    chatId: 'demo',
    rawMessages: baseMessages,
    floor: 1,
  });

  assert.equal(floorTwo.stat_data?.人物?.当前生命值, 15);
  assert.equal(floorThree.misc, 'kept');
  assert.equal(floorOne.stat_data?.人物?.名称, '癌骑士');
}

testComputeSnapshotUsesActiveSwipe();
testComputeSnapshotAccumulatesUpToFloor();
testResolverCachesWithoutChangingResults();

console.log('chat_reader_variable_merge_test: ok');
