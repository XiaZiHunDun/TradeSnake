import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWatchlistGroups, useSaveWatchlistGroups } from '../../shared/hooks/useApi'
import { Button, Input } from '../../shared/components/atoms'
import type { WatchlistGroup } from '../../shared/types'

const DEFAULT_COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']

export function Watchlist() {
  const navigate = useNavigate()
  const { data: groups, isLoading } = useWatchlistGroups()
  const { mutate: saveGroups } = useSaveWatchlistGroups()
  const [newGroupName, setNewGroupName] = useState('')
  const [newGroupCodes, setNewGroupCodes] = useState('')

  const handleCreateGroup = () => {
    if (!newGroupName.trim()) return
    const codes = newGroupCodes.split(',').map(c => c.trim()).filter(Boolean)
    const newGroup: WatchlistGroup = {
      id: Date.now().toString(),
      name: newGroupName,
      codes,
      color: DEFAULT_COLORS[(groups?.length ?? 0) % DEFAULT_COLORS.length],
    }
    saveGroups([...(groups || []), newGroup])
    setNewGroupName('')
    setNewGroupCodes('')
  }

  const handleDeleteGroup = (id: string) => {
    if (!groups) return
    saveGroups(groups.filter(g => g.id !== id))
  }

  const handleAddToGroup = (groupId: string, code: string) => {
    if (!groups || !code.trim()) return
    const updated = groups.map(g =>
      g.id === groupId ? { ...g, codes: [...g.codes, code.trim()] } : g
    )
    saveGroups(updated)
  }

  const handleRemoveFromGroup = (groupId: string, code: string) => {
    if (!groups) return
    const updated = groups.map(g =>
      g.id === groupId ? { ...g, codes: g.codes.filter(c => c !== code) } : g
    )
    saveGroups(updated)
  }

  if (isLoading) {
    return <div className="text-center py-12 text-gray-500">加载中...</div>
  }

  return (
    <div className="space-y-6">
      {/* 创建新分组 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">创建自选股分组</h2>
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm text-gray-500 mb-1">分组名称</label>
            <Input
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              placeholder="如: 我的重仓"
            />
          </div>
          <div className="flex-[2]">
            <label className="block text-sm text-gray-500 mb-1">股票代码 (逗号分隔)</label>
            <Input
              value={newGroupCodes}
              onChange={(e) => setNewGroupCodes(e.target.value)}
              placeholder="000001, 000002, 600519"
            />
          </div>
          <Button onClick={handleCreateGroup} variant="primary">
            创建
          </Button>
        </div>
      </div>

      {/* 分组列表 */}
      <div className="space-y-4">
        {groups && groups.length > 0 ? (
          groups.map((group) => (
            <div
              key={group.id}
              className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: group.color }}
                  />
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {group.name}
                  </h3>
                  <span className="text-sm text-gray-500">({group.codes.length}只)</span>
                </div>
                <Button
                  onClick={() => handleDeleteGroup(group.id)}
                  variant="secondary"
                  size="sm"
                >
                  删除
                </Button>
              </div>

              {group.codes.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {group.codes.map((code) => (
                    <div
                      key={code}
                      className="flex items-center gap-2 bg-gray-100 dark:bg-gray-700 rounded-lg px-3 py-1"
                    >
                      <button
                        onClick={() => navigate(`/stock/${code}`)}
                        className="text-blue-600 hover:text-blue-700 font-mono text-sm"
                      >
                        {code}
                      </button>
                      <button
                        onClick={() => handleRemoveFromGroup(group.id, code)}
                        className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-400 text-sm">暂无股票</div>
              )}

              {/* 添加股票 */}
              <div className="mt-4 flex gap-2">
                <Input
                  placeholder="添加股票代码"
                  className="w-32"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      const input = e.target as HTMLInputElement
                      handleAddToGroup(group.id, input.value)
                      input.value = ''
                    }
                  }}
                />
              </div>
            </div>
          ))
        ) : (
          <div className="text-center py-12 text-gray-500">
            暂无自选股分组，点击上方创建
          </div>
        )}
      </div>
    </div>
  )
}