'use client'
import { useTranslations } from 'next-intl'
import { useQuery, useMutation } from '@tanstack/react-query'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { settingsApi } from '@/lib/api'

const qc = new QueryClient()

const SECTIONS = [
  { key: 'general', icon: '🏢' },
  { key: 'apiKeys', icon: '🔑' },
  { key: 'emailInbox', icon: '📬' },
  { key: 'aiProvider', icon: '🤖' },
  { key: 'widgetConfig', icon: '💬' },
  { key: 'knowledgeBase', icon: '📚' },
  { key: 'aiRecruiter', icon: '✍️' },
]

function SettingsContent() {
  const t = useTranslations('settings')
  const [section, setSection] = useState('general')
  const [saved, setSaved] = useState(false)

  const { data: tenant } = useQuery({
    queryKey: ['tenant'],
    queryFn: () => settingsApi.getTenant(),
  })

  const { register, handleSubmit } = useForm({ values: tenant })

  const saveMutation = useMutation({
    mutationFn: (data: Parameters<typeof settingsApi.updateTenant>[0]) => settingsApi.updateTenant(data),
    onSuccess: () => { setSaved(true); setTimeout(() => setSaved(false), 2000) },
  })

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-white">{t('title')}</h1>

      <div className="flex gap-5">
        {/* Left nav */}
        <aside className="w-52 flex-shrink-0">
          <nav className="space-y-1">
            {SECTIONS.map(({ key, icon }) => (
              <button key={key} onClick={() => setSection(key)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-left transition-colors"
                style={{
                  background: section === key ? 'var(--cyan)15' : 'transparent',
                  color: section === key ? 'var(--cyan)' : '#94A3B8',
                }}>
                <span>{icon}</span>
                <span>{t(key as Parameters<typeof t>[0])}</span>
              </button>
            ))}
          </nav>
        </aside>

        {/* Content */}
        <div className="flex-1 rounded-xl border p-6" style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-border)' }}>
          <form onSubmit={handleSubmit((d) => saveMutation.mutate(d))} className="space-y-5">
            {section === 'general' && (
              <>
                <h2 className="text-base font-semibold text-white">{t('general')}</h2>
                {[
                  { name: 'name', label: 'Firm Name' },
                  { name: 'phone', label: 'Phone' },
                  { name: 'address', label: 'Address' },
                  { name: 'main_contact_name', label: 'Main Contact Name' },
                  { name: 'main_contact_email', label: 'Main Contact Email' },
                  { name: 'website_url', label: 'Website URL' },
                ].map(({ name, label }) => (
                  <div key={name}>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">{label}</label>
                    <input {...register(name as any)}
                      className="w-full px-3.5 py-2.5 rounded-lg text-sm text-white placeholder-slate-500 border outline-none focus:border-cyan-500 transition-colors"
                      style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}/>
                  </div>
                ))}
              </>
            )}

            {section === 'apiKeys' && (
              <>
                <h2 className="text-base font-semibold text-white">{t('apiKeys')}</h2>
                <p className="text-slate-400 text-sm">Your API keys are encrypted at rest. Leave blank to use platform defaults.</p>
                {[
                  { name: 'brightdata_api_key', label: 'BrightData API Key' },
                  { name: 'apollo_api_key', label: 'Apollo.io API Key' },
                  { name: 'hunter_api_key', label: 'Hunter.io API Key' },
                  { name: 'snov_api_key', label: 'Snov.io API Key' },
                  { name: 'sendgrid_api_key', label: 'SendGrid API Key' },
                  { name: 'ai_api_key', label: 'AI Provider API Key' },
                ].map(({ name, label }) => (
                  <div key={name}>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">{label}</label>
                    <input {...register(name as any)} type="password"
                      placeholder="••••••••••••••••"
                      className="w-full px-3.5 py-2.5 rounded-lg text-sm text-white placeholder-slate-500 border outline-none focus:border-cyan-500 transition-colors"
                      style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}/>
                  </div>
                ))}
              </>
            )}

            {section === 'emailInbox' && (
              <>
                <h2 className="text-base font-semibold text-white">{t('emailInbox')}</h2>
                {[
                  { name: 'email_inbox', label: 'Platform Inbox' },
                  { name: 'email_inbox_host', label: 'Custom IMAP Host' },
                  { name: 'email_inbox_port', label: 'IMAP Port' },
                  { name: 'email_inbox_user', label: 'IMAP Username' },
                ].map(({ name, label }) => (
                  <div key={name}>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">{label}</label>
                    <input {...register(name as any)}
                      className="w-full px-3.5 py-2.5 rounded-lg text-sm text-white placeholder-slate-500 border outline-none focus:border-cyan-500 transition-colors"
                      style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}/>
                  </div>
                ))}
              </>
            )}

            {section === 'aiProvider' && (
              <>
                <h2 className="text-base font-semibold text-white">{t('aiProvider')}</h2>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">AI Provider</label>
                  <select {...register('ai_provider')}
                    className="w-full px-3.5 py-2.5 rounded-lg text-sm text-white border outline-none focus:border-cyan-500 transition-colors cursor-pointer"
                    style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}>
                    <option value="anthropic">Anthropic (Claude Sonnet)</option>
                    <option value="openai">OpenAI (GPT-4)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Search Provider</label>
                  <select {...register('search_provider')}
                    className="w-full px-3.5 py-2.5 rounded-lg text-sm text-white border outline-none focus:border-cyan-500 transition-colors cursor-pointer"
                    style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}>
                    <option value="scrapingdog">ScrapingDog</option>
                    <option value="brightdata">BrightData</option>
                    <option value="both">Both</option>
                  </select>
                </div>
              </>
            )}

            {section === 'aiRecruiter' && (
              <>
                <h2 className="text-base font-semibold text-white">{t('aiRecruiter')}</h2>
                <p className="text-slate-400 text-sm">Customise the AI Recruiter&apos;s behaviour in plain English. Leave blank to use the platform default.</p>
                <textarea
                  {...register('ai_recruiter_config' as any)}
                  rows={10}
                  placeholder="E.g. Always ask about team culture preferences. Focus on remote-friendly candidates..."
                  className="w-full px-3.5 py-2.5 rounded-lg text-sm text-white placeholder-slate-500 border outline-none focus:border-cyan-500 transition-colors resize-none"
                  style={{ background: 'var(--navy)', borderColor: 'var(--navy-border)' }}
                />
              </>
            )}

            {(section === 'widgetConfig' || section === 'knowledgeBase') && (
              <div className="text-center py-8 text-slate-400 text-sm">
                {section === 'widgetConfig' ? 'Widget configuration coming soon.' : 'Knowledge base management coming soon.'}
              </div>
            )}

            <div className="flex items-center gap-3 pt-2 border-t" style={{ borderColor: 'var(--navy-border)' }}>
              <button type="submit" disabled={saveMutation.isPending}
                className="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
                style={{ background: 'var(--blue)' }}>
                {saveMutation.isPending ? 'Saving...' : t('save')}
              </button>
              {saved && <span className="text-green-400 text-sm">✓ Saved</span>}
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

export default function SettingsPage() {
  return <QueryClientProvider client={qc}><SettingsContent /></QueryClientProvider>
}
