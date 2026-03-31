import { X, TrendingUp, DollarSign, Sparkles, Activity, Shield, Zap, BookOpen, CheckCircle, ArrowRight } from 'lucide-react'

export function FormulaEducation({ isOpen, onClose }) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-card-bg rounded-xl border border-border-dark max-w-2xl w-full max-h-[85vh] overflow-y-auto shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="sticky top-0 bg-card-bg border-b border-border-dark p-4 flex items-center justify-between rounded-t-xl">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-accent-blue/20 flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-accent-blue" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">战力学堂</h2>
              <p className="text-xs text-gray-400">了解战力值背后的秘密</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* 核心理念 */}
          <div className="bg-gradient-to-r from-accent-blue/10 to-cp-high/10 rounded-xl p-5 border border-accent-blue/20">
            <div className="flex items-start gap-3">
              <Zap className="w-6 h-6 text-accent-blue flex-shrink-0 mt-1" />
              <div>
                <h3 className="text-white font-bold mb-2">核心理念</h3>
                <p className="text-gray-300 text-sm leading-relaxed">
                  战力值 = 股票的"赚钱能力分数"（0-100分）。就像贪吃蛇吃高分食物快速长大，
                  <span className="text-cp-high font-medium">持有高战力股票</span>能让你的投资组合更快速增值！
                </p>
              </div>
            </div>
          </div>

          {/* 公式 */}
          <div>
            <h3 className="text-white font-bold mb-3 flex items-center gap-2">
              <Activity className="w-5 h-5 text-cp-high" />
              战力公式 v14
            </h3>
            <div className="bg-deep-night rounded-xl p-4 border border-border-dark">
              <div className="text-center mb-4">
                <p className="text-lg text-white font-medium">
                  总战力 = <span className="text-cp-high">(成长分×30% + 价值分×25% + 质量分×20% + 动量分×15%)</span> × 风险调整
                </p>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <p className="text-gray-400 mb-1">成长分</p>
                  <p className="text-accent-blue font-bold">30%</p>
                </div>
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <p className="text-gray-400 mb-1">价值分</p>
                  <p className="text-cp-high font-bold">25%</p>
                </div>
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <p className="text-gray-400 mb-1">质量分</p>
                  <p className="text-purple-400 font-bold">20%</p>
                </div>
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <p className="text-gray-400 mb-1">动量分</p>
                  <p className="text-yellow-400 font-bold">15%</p>
                </div>
              </div>
            </div>
          </div>

          {/* 各因子详解 */}
          <div className="space-y-4">
            <h3 className="text-white font-bold">各因子详解</h3>

            {/* 成长分 */}
            <div className="bg-white/5 rounded-xl p-4 border-l-4 border-accent-blue">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-5 h-5 text-accent-blue" />
                <h4 className="text-white font-medium">成长分 (30%)</h4>
              </div>
              <p className="text-gray-400 text-sm mb-2">衡量公司业绩增长速度</p>
              <div className="bg-deep-night rounded-lg p-3 text-sm">
                <p className="text-gray-300">成长分 = 净利润增长×60% + 营收增长×40%</p>
                <p className="text-gray-500 text-xs mt-1">净利润增长限制0-300%，营收增长限制-50%~100%</p>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span>高成长的公司更有未来</span>
              </div>
            </div>

            {/* 价值分 */}
            <div className="bg-white/5 rounded-xl p-4 border-l-4 border-cp-high">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-5 h-5 text-cp-high" />
                <h4 className="text-white font-medium">价值分 (25%)</h4>
              </div>
              <p className="text-gray-400 text-sm mb-2">衡量股票估值是否合理</p>
              <div className="bg-deep-night rounded-lg p-3 text-sm space-y-2">
                <p className="text-gray-300">• ROE（净资产收益率）：越高越好，>15%为优质</p>
                <p className="text-gray-300">• PE（市盈率）：5-20区间最优，过高有泡沫风险</p>
                <p className="text-gray-300">• PEG = PE/净利润增长率：&lt;1表示被低估</p>
                <p className="text-gray-300">• PB（市净率）：&lt;1为破净，价值凸显</p>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span>低估值+高ROE = 性价比之王</span>
              </div>
            </div>

            {/* 质量分 */}
            <div className="bg-white/5 rounded-xl p-4 border-l-4 border-purple-500">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-5 h-5 text-purple-400" />
                <h4 className="text-white font-medium">质量分 (20%)</h4>
              </div>
              <p className="text-gray-400 text-sm mb-2">衡量盈利质量高低</p>
              <div className="bg-deep-night rounded-lg p-3 text-sm space-y-2">
                <p className="text-gray-300">• 现金流：正现金流+高ROE = 真盈利</p>
                <p className="text-gray-300">• 毛利率：&gt;30%表示有护城河（品牌/技术/垄断）</p>
                <p className="text-gray-300">• 资产负债率：&lt;50%表示财务稳健</p>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span>有利润无现金流的要小心！</span>
              </div>
            </div>

            {/* 动量分 */}
            <div className="bg-white/5 rounded-xl p-4 border-l-4 border-yellow-400">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-5 h-5 text-yellow-400" />
                <h4 className="text-white font-medium">动量分 (15%)</h4>
              </div>
              <p className="text-gray-400 text-sm mb-2">衡量短期趋势强弱</p>
              <div className="bg-deep-night rounded-lg p-3 text-sm">
                <p className="text-gray-300">动量分 = 当日涨跌幅（限制在-10%~+10%）</p>
                <p className="text-gray-500 text-xs mt-1">涨多了会回调，跌多了会反弹，动量是短期指标</p>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
                <CheckCircle className="w-4 h-4 text-yellow-500" />
                <span>动量是"顺势而为"，不是"追涨杀跌"</span>
              </div>
            </div>
          </div>

          {/* 风险调整 */}
          <div className="bg-white/5 rounded-xl p-4 border border-red-500/30">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-5 h-5 text-red-400" />
              <h4 className="text-white font-medium">风险调整</h4>
            </div>
            <p className="text-gray-400 text-sm mb-2">高风险股票的战力会打折</p>
            <div className="bg-deep-night rounded-lg p-3 text-sm">
              <p className="text-gray-300">最终战力 = 基础战力 × (1 - 风险分/100 × 10%)</p>
              <p className="text-gray-500 text-xs mt-1">风险分基于PE、ROE、增长稳定性、波动率计算</p>
            </div>
          </div>

          {/* 实战口诀 */}
          <div className="bg-gradient-to-r from-cp-high/20 to-accent-blue/20 rounded-xl p-5 border border-cp-high/30">
            <h3 className="text-white font-bold mb-3 flex items-center gap-2">
              <Zap className="w-5 h-5 text-cp-high" />
              实战口诀
            </h3>
            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <ArrowRight className="w-5 h-5 text-cp-high flex-shrink-0 mt-0.5" />
                <p className="text-gray-300 text-sm"><span className="text-cp-high font-medium">价值型</span>：PEG&lt;1 + ROE&gt;15% + 正现金流 = 稳健之选</p>
              </div>
              <div className="flex items-start gap-3">
                <ArrowRight className="w-5 h-5 text-accent-blue flex-shrink-0 mt-0.5" />
                <p className="text-gray-300 text-sm"><span className="text-accent-blue font-medium">成长型</span>：净利润增长&gt;30% + 营收增长&gt;20% = 潜力股</p>
              </div>
              <div className="flex items-start gap-3">
                <ArrowRight className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
                <p className="text-gray-300 text-sm"><span className="text-purple-400 font-medium">质量型</span>：毛利率&gt;30% + 负债率&lt;50% + 正现金流 = 优等生</p>
              </div>
            </div>
          </div>

          {/* 免责声明 */}
          <div className="text-center text-xs text-gray-500 pt-4 border-t border-border-dark">
            <p>战力值仅供参考，不构成投资建议</p>
            <p>市场有风险，投资需谨慎</p>
          </div>
        </div>
      </div>
    </div>
  )
}
