import { useState, useEffect } from 'react'
import { Zap, List, Search, User, Sparkles, X, ChevronRight } from 'lucide-react'

const STORAGE_KEY = 'tradesnake_tour_done'

const steps = [
  {
    target: '[class*="header"]',
    title: '欢迎使用股市贪吃蛇',
    content: '这是一个用"战力值"衡量股票价值的工具，帮助你找到高战力股票来提升组合整体实力。',
    icon: Zap
  },
  {
    target: 'button:has-text("战力榜单")',
    title: '战力榜单',
    content: '查看所有股票的战力排名，可以排序、筛选、添加自选。战力越高，股票质量越好。',
    icon: List
  },
  {
    target: 'button:has-text("单股查询")',
    title: '单股查询',
    content: '输入股票代码，查看单只股票的详细战力分析，包括雷达图和历史走势。',
    icon: Search
  },
  {
    target: 'button:has-text("我的战力")',
    title: '我的战力',
    content: '管理你的持仓组合，计算个人总战力。战力贡献 = 持股数量 × 股票战力值。',
    icon: User
  },
  {
    target: 'button:has-text("智能推荐")',
    title: '智能推荐',
    content: '根据不同策略推荐股票：价值型（高ROE+低PE）、成长型（高增长）、趋势型（动量强）。',
    icon: Sparkles
  }
]

export function useTourGuide() {
  const [isActive, setIsActive] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)

  useEffect(() => {
    const hasDone = localStorage.getItem(STORAGE_KEY)
    if (!hasDone) {
      setIsActive(true)
    }
  }, [])

  const startTour = () => {
    setCurrentStep(0)
    setIsActive(true)
  }

  const skipTour = () => {
    localStorage.setItem(STORAGE_KEY, 'true')
    setIsActive(false)
  }

  const nextStep = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1)
    } else {
      skipTour()
    }
  }

  return { isActive, currentStep, steps, startTour, skipTour, nextStep }
}

export function TourGuide({ isActive, currentStep, steps, skipTour, nextStep }) {
  if (!isActive) return null

  const step = steps[currentStep]
  const Icon = step.icon

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-card-bg rounded-xl border border-border-dark p-6 max-w-md w-full shadow-2xl">
        <div className="flex items-start gap-4 mb-4">
          <div className="w-12 h-12 rounded-lg bg-accent-blue/20 flex items-center justify-center flex-shrink-0">
            <Icon className="w-6 h-6 text-accent-blue" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-bold text-white mb-1">{step.title}</h3>
            <p className="text-gray-400 text-sm">{step.content}</p>
          </div>
        </div>

        <div className="flex items-center justify-between">
          {/* 步骤指示器 */}
          <div className="flex gap-1">
            {steps.map((_, i) => (
              <div
                key={i}
                className={`w-2 h-2 rounded-full ${
                  i === currentStep ? 'bg-accent-blue' : i < currentStep ? 'bg-accent-blue/50' : 'bg-gray-600'
                }`}
              />
            ))}
          </div>

          <div className="flex gap-2">
            <button
              onClick={skipTour}
              className="px-3 py-2 text-gray-400 hover:text-white text-sm transition-colors"
            >
              跳过
            </button>
            <button
              onClick={nextStep}
              className="flex items-center gap-1 px-4 py-2 bg-accent-blue text-white rounded-lg hover:bg-accent-blue/80 transition-colors text-sm"
            >
              {currentStep < steps.length - 1 ? '下一步' : '开始使用'}
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
