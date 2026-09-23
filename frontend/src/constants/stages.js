// 8 个投递阶段：key 存库，label/颜色用于展示（彩色阶段看板）
export const STAGES = [
  { key: 'not_started', label: '未开始', color: '#909399', bg: '#f0f2f5' },
  { key: 'applied', label: '已投递', color: '#277b75', bg: '#e3f7f1' },
  { key: 'screening', label: '简历筛选', color: '#7367f0', bg: '#f0ecff' },
  { key: 'written_test', label: '笔试', color: '#f59e0b', bg: '#fdf3e0' },
  { key: 'interview', label: '面试', color: '#238d80', bg: '#dff8f0' },
  { key: 'offer', label: 'Offer', color: '#f43f5e', bg: '#fdecef' },
  { key: 'rejected', label: '已拒绝', color: '#64748b', bg: '#eef1f5' },
  { key: 'withdrawn', label: '已撤回', color: '#94a3b8', bg: '#f1f5f9' },
]

export const STAGE_MAP = Object.fromEntries(STAGES.map((s) => [s.key, s]))

// 安排类型（未来安排页徽章展示）
export const SCHEDULE_TYPES = ['笔试', '一面', '二面', 'HR面', '终面', '其他']

export const TYPE_COLORS = {
  笔试: '#f59e0b',
  一面: '#10b981',
  二面: '#277b75',
  'HR面': '#7367f0',
  终面: '#f43f5e',
  其他: '#909399',
}
