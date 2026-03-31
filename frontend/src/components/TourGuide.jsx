import { useState, useEffect } from 'react'
import { Zap, List, User, Sparkles, X, ChevronRight, BookOpen, TrendingUp, Shield } from 'lucide-react'

const STORAGE_KEY = 'tradesnake_tour_done_v2'

// 增强版引导步骤
const steps = [
  {
    target: '[class*="header"]',
    title: '欢迎使用股市贪吃蛇',
    content: '核心理念：用"战力值"代替金钱，像贪吃蛇一样通过"换股"来提升组合整体实力！战力越高，股票越值得持有。',
    icon: Zap
  },
  {
    target: '[class*="header"]',
    title: '战力是什么？',
    content: '战力值 = 股票的"赚钱能力分数"（0-100分）。类比：贪吃蛇里，吃高分食物才能快速长大；股市里，持高战力股票才能稳健增值。',
    icon: TrendingUp,
    isTip: true
  },
  {
    target: 'button:has-text("战力榜单")',
    title: '战力榜单',
    content: '查看所有股票的战力排名。绿色=高战力(70+)，黄色=中战力(50-70)，红色=低战力(<50)。战力70+的股票值得关注！',
    icon: List
  },
  {
    target: 'button:has-text("我的战力")',
    title: '我的战力',
    content: '管理持仓，计算个人总战力。总战力 = Σ(持股数 × 战力值)。如果持仓平均战力低于市场TOP10，该考虑换股了！',
    icon: User
  },
  {
    target: 'button:has-text("智能推荐")',
    title: '智能推荐',
    content: '三种策略选股：价值型（低估稳健）、成长型（高增长潜力）、趋势型（顺势而为）。选对策略，事半功倍！',
    icon: Sparkles
  },
  {
    target: 'button:has-text("战力榜单")',
    title: '实战技巧',
    content: '查看战力榜TOP10，将自己的持仓与它们对比。如果持仓股战力低于50，考虑用TOP10中的股票替换，这就是"换股升级"！',
    icon: Shield,
    isTip: true
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

  const resetTour = () => {
    localStorage.removeItem(STORAGE_KEY)
    setIsActive(true)
    setCurrentStep(0)
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

  return { isActive, currentStep, steps, startTour, resetTour, skipTour, nextStep }
}

export function TourGuide({ isActive, currentStep, steps, skipTour, nextStep }) {
  if (!isActive) return null

  const step = steps[currentStep]
  const Icon = step.icon

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div className={`bg-card-bg rounded-xl border p-6 max-w-md w-full shadow-2xl ${
        step.isTip ? 'border-accent-blue/50' : 'border-border-dark'
      }`}>
        {/* 提示标签 */}
        {step.isTip && (
          <div className="mb-3 flex items-center gap-2">
            <span className="px-2 py-0.5 bg-accent-blue/20 text-accent-blue text-xs rounded-full flex items-center gap-1">
              <BookOpen className="w-3 h-3" />
              战力小知识
            </span>
          </div>
        )}

        <div className="flex items-start gap-4 mb-5">
          <div className={`w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0 ${
            step.isTip ? 'bg-accent-blue/20' : 'bg-cp-high/20'
          }`}>
            <Icon className={`w-6 h-6 ${step.isTip ? 'text-accent-blue' : 'text-cp-high'}`} />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-bold text-white mb-1">{step.title}</h3>
            <p className="text-gray-300 text-sm leading-relaxed">{step.content}</p>
          </div>
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-border-dark">
          {/* 步骤指示器 */}
          <div className="flex gap-1.5">
            {steps.map((_, i) => (
              <div
                key={i}
                className={`w-2 h-2 rounded-full transition-colors ${
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
              跳过引导
            </button>
            <button
              onClick={nextStep}
              className="flex items-center gap-1 px-4 py-2 bg-accent-blue text-white rounded-lg hover:bg-accent-blue/80 transition-colors text-sm font-medium"
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
