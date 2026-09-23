/**
 * 把接口错误转成可读的中文提示。
 * FastAPI 的 422 校验错误 detail 是数组（如字段为空/格式错误），
 * 这里解析成「字段名 + 原因」，避免界面显示 [object Object]。
 */
const FIELD_LABELS = {
  company_name: '公司',
  position: '岗位',
  channel: '渠道',
  apply_date: '投递日期',
  current_stage: '当前阶段',
  notes: '备注',
  company_id: '公司',
  title: '标题',
  type: '类型',
  sched_date: '日期',
  sched_time: '时间',
  link: '链接',
  location: '地点',
  name: '名称',
  industry: '行业',
  website: '官网',
  username: '用户名',
  password: '密码',
}

export function formatApiError(e) {
  const detail = e?.response?.data?.detail
  if (Array.isArray(detail)) {
    // FastAPI 422: [{"loc":["body","apply_date"],"msg":"...","type":"..."}]
    const msgs = detail.map((item) => {
      const field = FIELD_LABELS[item.loc?.[item.loc.length - 1]] || item.loc?.join('.')
      return `${field ? `「${field}」` : ''}${item.msg ? '：' + item.msg : '格式有误'}`
    })
    return msgs.join('；')
  }
  if (typeof detail === 'string') return detail
  if (e?.message) return e.message
  return '请求失败，请稍后重试'
}
