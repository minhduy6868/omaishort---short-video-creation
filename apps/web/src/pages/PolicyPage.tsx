import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { SUPPORTED_LANGS, type SupportedLang } from "../i18n";
import { useSEO } from "../hooks/useSEO";
import { Header } from "../components/layout/Header";
import { Footer } from "../components/layout/Footer";
import "../styles/landing.css";

export type PolicySection = "privacy" | "terms" | "cookies";

type PolicyCard = {
  code: string;
  title: string;
  body: string[];
};

type PolicyCopy = {
  kicker: string;
  updated: string;
  tabs: Record<PolicySection, string>;
  sections: Record<
    PolicySection,
    {
      title: string;
      subtitle: string;
      cards: PolicyCard[];
    }
  >;
};

const POLICY_COPY: Record<SupportedLang, PolicyCopy> = {
  vi: {
    kicker: "Chính sách & Pháp lý",
    updated: "Cập nhật lần cuối: 07/11/2026",
    tabs: {
      privacy: "Chính sách Bảo mật",
      terms: "Điều khoản Dịch vụ",
      cookies: "Cookie & Dữ liệu Local",
    },
    sections: {
      privacy: {
        title: "Chính sách Bảo mật",
        subtitle:
          "omaishort vận hành theo kiến trúc hybrid: file video MP4 lưu trữ trực tiếp trên ổ đĩa local của máy render, trong khi tài khoản và metadata được bảo vệ trên Cloudflare D1.",
        cards: [
          {
            code: "01",
            title: "Phân tách dữ liệu Local và Cloudflare D1",
            body: [
              "Toàn bộ file video MP4 đầu ra (1080×1920 @ 30fps), file âm thanh giọng đọc (.mp3/.wav) và phụ đề karaoke (.ass) được lưu tại thư mục local data/jobs/<id>/ trên máy chủ render.",
              "Cơ sở dữ liệu Cloudflare D1 lưu thông tin tài khoản (email, mật khẩu băm PBKDF2-HMAC-SHA256), cấu trúc kịch bản JSON, lịch sử job, cài đặt giao diện và bản sao lưu tệp đính kèm nhỏ (ảnh khuôn mặt tham chiếu, logo, kịch bản).",
            ],
          },
          {
            code: "02",
            title: "Không bán dữ liệu & Không theo dõi quảng cáo",
            body: [
              "omaishort không tích hợp mạng quảng cáo bên thứ ba, không thu thập hành vi duyệt web ngoài phạm vi ứng dụng và không bán dữ liệu người dùng cho bất kỳ bên thứ ba nào.",
              "Nội dung văn bản, URL bài báo hoặc chủ đề bạn nhập chỉ được gửi tới các nhà cung cấp AI được cấu hình (OpenAI, Gemini, xAI Grok, ElevenLabs hoặc Microsoft Edge-TTS) để phục vụ trực tiếp cho quá trình tạo kịch bản, ảnh tĩnh và giọng đọc.",
            ],
          },
          {
            code: "03",
            title: "Bảo mật thông tin xác thực & Khóa API",
            body: [
              "Mật khẩu người dùng được băm một chiều bằng thuật toán PBKDF2-HMAC-SHA256 kèm salt ngẫu nhiên trước khi lưu vào Cloudflare D1.",
              "Refresh token được băm SHA-256 trong cơ sở dữ liệu và có thể bị thu hồi bất cứ lúc nào khi người dùng đăng xuất hoặc khi Quản trị viên (operator) thu hồi phiên.",
            ],
          },
          {
            code: "04",
            title: "Quyền kiểm soát, Thu gọn và Xóa dữ liệu",
            body: [
              "Bạn có quyền xem, tải xuống file MP4 hoặc xóa các tệp đính kèm trong trang Tài khoản (/account).",
              "Quản trị viên hệ thống có thể sử dụng tính năng Thu gọn (Compact) để xóa các tệp trung gian (stills, refs, tts, captions) sau khi render xong chỉ giữ lại file short.mp4, hoặc xóa vĩnh viễn toàn bộ bản ghi job trên cả Cloudflare D1 và đĩa cứng local.",
            ],
          },
        ],
      },
      terms: {
        title: "Điều khoản Dịch vụ",
        subtitle:
          "Quy định sử dụng nền tảng omaishort Studio, quyền sở hữu nội dung đầu ra và trách nhiệm khi kết nối các nhà cung cấp AI.",
        cards: [
          {
            code: "01",
            title: "Phạm vi dịch vụ & Phân quyền tài khoản",
            body: [
              "Hệ thống hỗ trợ hai cấp tài khoản: Quản trị viên (operator) quản lý cấu hình hệ thống, nhà cung cấp AI, kho lưu trữ video local và danh sách người dùng; Người sáng tạo (creator) sử dụng Studio để tạo video ngắn ở 3 định dạng Drama, News và Knowledge.",
              "Quản trị viên có quyền bật hoặc tắt tính năng tự đăng ký tài khoản mới (/register) hoặc tạm khóa các tài khoản vi phạm quy định vận hành.",
            ],
          },
          {
            code: "02",
            title: "Quyền sở hữu nội dung & Bản quyền",
            body: [
              "Bạn giữ toàn bộ quyền đối với kịch bản gốc, hình ảnh khuôn mặt tham chiếu (Character Bible), logo và tài liệu mà bạn tải lên hệ thống.",
              "Khi sử dụng chế độ News (tin tức từ URL) hoặc Knowledge (kiến thức), bạn chịu trách nhiệm đảm bảo nội dung xuất bản tuân thủ quy định trích dẫn nguồn và bản quyền tại quốc gia hoặc nền tảng mạng xã hội nơi bạn đăng tải.",
            ],
          },
          {
            code: "03",
            title: "Quy tắc sử dụng hợp lệ",
            body: [
              "Nghiêm cấm sử dụng omaishort để tạo nội dung giả mạo danh tính bất hợp pháp, phát tán mã độc, thông tin sai lệch gây hại hoặc nội dung vi phạm pháp luật hiện hành.",
              "Không được can thiệp trái phép vào các giao diện quản trị (/admin), không lạm dụng hàng đợi render làm quá tải tài nguyên FFmpeg của máy chủ.",
            ],
          },
          {
            code: "04",
            title: "Kết nối Nhà cung cấp bên thứ ba",
            body: [
              "Pipeline omaishort kết nối với các dịch vụ AI thông qua API hoặc phiên trình duyệt của Quản trị viên (ChatGPT Web, Grok Imagine, Gemini API, ElevenLabs, Edge-TTS, Pollinations). Việc sử dụng các dịch vụ này đồng thời chịu sự điều chỉnh bởi điều khoản của từng nhà cung cấp tương ứng.",
            ],
          },
        ],
      },
      cookies: {
        title: "Chính sách Cookie & Dữ liệu Local",
        subtitle:
          "Chi tiết các cookie thiết yếu, bộ nhớ trình duyệt (localStorage) và hồ sơ lưu trữ local được omaishort sử dụng.",
        cards: [
          {
            code: "01",
            title: "Cookie xác thực thiết yếu (HttpOnly)",
            body: [
              "omaishort chỉ sử dụng duy nhất một cookie thiết yếu tên là omaishort_rt (HttpOnly, SameSite=Lax) tại đường dẫn /auth để duy trì phiên đăng nhập an toàn và cấp lại JWT access token ngắn hạn.",
              "Hệ thống không sử dụng bất kỳ cookie theo dõi, cookie phân tích bên thứ ba hay pixel tiếp thị lại nào.",
            ],
          },
          {
            code: "02",
            title: "Bộ nhớ trình duyệt (localStorage)",
            body: [
              "i18nextLng: Lưu ngôn ngữ hiển thị bạn đã chọn (vi, en hoặc ja).",
              "omaishort.theme: Lưu giao diện hiển thị đồng bộ toàn trang (brutal hoặc soft) để tránh hiện tượng nhấp nháy giao diện khi tải trang.",
            ],
          },
          {
            code: "03",
            title: "Hồ sơ Chrome Hub trên máy chủ (Chỉ dành cho Admin)",
            body: [
              "Khi Quản trị viên (operator) đăng nhập ChatGPT Web hoặc Grok Imagine, phiên làm việc được lưu trong thư mục riêng biệt data/chatgpt-web/profile và data/grok-web/profile trên máy chủ render.",
              "Các hồ sơ này hoàn toàn tách biệt với tài khoản của người dùng thường (creator) và không hiển thị trong giao diện của tài khoản creator.",
            ],
          },
          {
            code: "04",
            title: "Lưu trữ Video MP4 Local",
            body: [
              "Mỗi job tạo video sinh ra thư mục data/jobs/<id>/ chứa kịch bản, ảnh tĩnh, âm thanh và file kết quả render/short.mp4.",
              "Thông số dung lượng MP4 và trạng thái đĩa được đồng bộ lên trường storage_json trên Cloudflare D1 để Quản trị viên dễ dàng kiểm tra và dọn dẹp.",
            ],
          },
        ],
      },
    },
  },
  en: {
    kicker: "Legal & Policies",
    updated: "Last updated: November 7, 2026",
    tabs: {
      privacy: "Privacy Policy",
      terms: "Terms of Service",
      cookies: "Cookie & Data Policy",
    },
    sections: {
      privacy: {
        title: "Privacy Policy",
        subtitle:
          "omaishort runs a hybrid architecture: rendered 1080×1920 MP4 videos stay on your local render disk, while accounts and job metadata sync to Cloudflare D1.",
        cards: [
          {
            code: "01",
            title: "Local Video Storage vs. Cloudflare D1 Metadata",
            body: [
              "Rendered 1080×1920 @ 30fps MP4 videos, synthesized narration audio (.mp3/.wav), and ASS karaoke captions are stored locally under data/jobs/<id>/ on the render host.",
              "Cloudflare D1 stores account records (email, PBKDF2-HMAC-SHA256 password hashes), storyboard JSON, job status history, site theme settings, and small attachment backups (reference faces, logos, scripts).",
            ],
          },
          {
            code: "02",
            title: "Zero Ad Tracking & No Data Resale",
            body: [
              "omaishort embeds no third-party ad networks, no cross-site tracking pixels, and never sells or rents user data.",
              "Scripts, news URLs, and topics you submit are sent only to the configured AI providers (OpenAI, Gemini, xAI Grok, ElevenLabs, or Microsoft Edge-TTS) strictly to generate your video scenes and voiceover.",
            ],
          },
          {
            code: "03",
            title: "Credential & Token Security",
            body: [
              "User passwords are hashed with PBKDF2-HMAC-SHA256 and per-user random salts before persistence in Cloudflare D1.",
              "Refresh tokens are stored as SHA-256 hashes and can be revoked immediately upon sign-out or by a system Operator.",
            ],
          },
          {
            code: "04",
            title: "Data Retention, Compaction & Deletion",
            body: [
              "Creators can view and download their rendered MP4s or remove uploaded attachments from the Account page (/account).",
              "System Operators can compact completed jobs (removing intermediate stills, audio chunks, and caption drafts while keeping short.mp4) or permanently delete job records from both Cloudflare D1 and local storage.",
            ],
          },
        ],
      },
      terms: {
        title: "Terms of Service",
        subtitle:
          "Terms governing the use of omaishort Studio, content ownership, role permissions, and third-party AI provider integrations.",
        cards: [
          {
            code: "01",
            title: "Account Roles & Access Control",
            body: [
              "omaishort supports two roles: Operators (administrators who manage system settings, provider hubs, local video storage, and user accounts) and Creators (users who create Drama, News, and Knowledge short videos).",
              "Operators may enable or disable public registration (/register) and suspend accounts that violate operational rules.",
            ],
          },
          {
            code: "02",
            title: "Content Ownership & Attribution",
            body: [
              "You retain full ownership of your original scripts, character reference photos, logos, and uploaded source materials.",
              "When generating editorial News or Knowledge videos from external URLs or topics, you are responsible for complying with applicable copyright and source attribution standards where you publish.",
            ],
          },
          {
            code: "03",
            title: "Acceptable Use",
            body: [
              "You may not use omaishort to generate unlawful impersonations, malicious content, or material that violates applicable laws.",
              "Do not attempt unauthorized access to administrative endpoints (/admin) or abuse the FFmpeg render queue.",
            ],
          },
          {
            code: "04",
            title: "Third-Party AI Providers",
            body: [
              "omaishort integrates with external AI services configured by the Operator (ChatGPT Web, Grok Imagine, Gemini API, ElevenLabs, Edge-TTS, Pollinations). Use of those underlying models is subject to each provider's respective terms.",
            ],
          },
        ],
      },
      cookies: {
        title: "Cookie & Local Storage Policy",
        subtitle:
          "How omaishort uses essential authentication cookies, browser localStorage, and local disk directories.",
        cards: [
          {
            code: "01",
            title: "Essential Authentication Cookie (HttpOnly)",
            body: [
              "omaishort sets a single essential cookie named omaishort_rt (HttpOnly, SameSite=Lax) scoped to /auth to maintain your signed-in session and refresh short-lived JWT access tokens.",
              "We do not set advertising, behavioral profiling, or third-party analytics cookies.",
            ],
          },
          {
            code: "02",
            title: "Browser localStorage Preferences",
            body: [
              "i18nextLng: Remembers your selected interface language (vi, en, or ja).",
              "omaishort.theme: Caches the active site skin (brutal or soft) so pages render without theme flicker.",
            ],
          },
          {
            code: "03",
            title: "Host Chrome Hub Profiles (Operators Only)",
            body: [
              "When an Operator connects ChatGPT Web or Grok Imagine, the persistent Chromium profile is stored under data/chatgpt-web/profile and data/grok-web/profile on the host machine.",
              "These provider hub controls are restricted to Operators and are hidden from Creator accounts.",
            ],
          },
          {
            code: "04",
            title: "Local MP4 Disk Artifacts",
            body: [
              "Each render job writes its output to data/jobs/<id>/render/short.mp4 on the local disk and syncs byte size and file status to storage_json in Cloudflare D1.",
            ],
          },
        ],
      },
    },
  },
  ja: {
    kicker: "ポリシー・利用規約",
    updated: "最終更新日: 2026年11月7日",
    tabs: {
      privacy: "プライバシーポリシー",
      terms: "利用規約",
      cookies: "Cookie・データポリシー",
    },
    sections: {
      privacy: {
        title: "プライバシーポリシー",
        subtitle:
          "omaishortはハイブリッド構成を採用しています。生成されたMP4動画はローカルディスクに保存され、アカウントとメタデータはCloudflare D1で保護されます。",
        cards: [
          {
            code: "01",
            title: "ローカル動画保存とCloudflare D1メタデータの分離",
            body: [
              "レンダリングされた1080×1920（30fps）のMP4動画、音声ファイル（.mp3/.wav）、およびASSカラオケ字幕は、レンダーホストの data/jobs/<id>/ にローカル保存されます。",
              "Cloudflare D1には、アカウント情報（メールアドレス、PBKDF2-HMAC-SHA256ハッシュ化パスワード）、絵コンテJSON、ジョブ履歴、サイトテーマ設定、および添付ファイルが保存されます。",
            ],
          },
          {
            code: "02",
            title: "広告トラッキングなし・データ販売なし",
            body: [
              "omaishortは第三者の広告ネットワークや追跡ピクセルを使用せず、ユーザーデータを第三者に販売することはありません。",
              "入力されたスクリプトやURLは、動画生成に必要なAIプロバイダー（OpenAI、Gemini、xAI Grok、ElevenLabs、Edge-TTSなど）にのみ送信されます。",
            ],
          },
          {
            code: "03",
            title: "認証情報とトークンの保護",
            body: [
              "パスワードはランダムソルト付きのPBKDF2-HMAC-SHA256でハッシュ化され、リフレッシュトークンはSHA-256ハッシュとしてCloudflare D1に記録されます。",
            ],
          },
          {
            code: "04",
            title: "データの圧縮（Compact）と削除",
            body: [
              "ユーザーはアカウントページ（/account）からMP4動画のダウンロードや添付ファイルの削除を行えます。",
              "管理者（operator）は、中間ファイルを削除してMP4のみを残す圧縮機能や、Cloudflare D1およびローカルディスクからの完全削除を実行できます。",
            ],
          },
        ],
      },
      terms: {
        title: "利用規約",
        subtitle:
          "omaishort Studioの利用条件、コンテンツの権利、およびAIプロバイダー連携に関する規約。",
        cards: [
          {
            code: "01",
            title: "アカウント権限とロール",
            body: [
              "システムには管理者（operator）とクリエイター（creator）の2種類のロールがあります。管理者はシステム設定、AIプロバイダーハブ、ローカル動画ストレージ、ユーザー管理を行います。",
            ],
          },
          {
            code: "02",
            title: "コンテンツの所有権",
            body: [
              "アップロードされたオリジナル脚本、キャラクター参照画像、ロゴの権利はユーザーに帰属します。ニュースURLや外部トピックを利用する場合は、公開先の著作権および引用ルールを遵守してください。",
            ],
          },
          {
            code: "03",
            title: "禁止事項",
            body: [
              "違法ななりすまし、悪意のあるコンテンツの生成、管理エンドポイント（/admin）への不正アクセス、およびレンダーキューの濫用を禁止します。",
            ],
          },
          {
            code: "04",
            title: "外部AIプロバイダーの利用",
            body: [
              "ChatGPT Web、Grok Imagine、Gemini API、ElevenLabs、Edge-TTS、Pollinationsなどの外部プロバイダー連携は、各サービス提供元の利用規約に従います。",
            ],
          },
        ],
      },
      cookies: {
        title: "Cookie・ローカルデータポリシー",
        subtitle:
          "必須の認証Cookie、ブラウザのlocalStorage、およびローカルディスクデータの取り扱いについて。",
        cards: [
          {
            code: "01",
            title: "必須の認証Cookie（HttpOnly）",
            body: [
              "omaishortはログインセッション維持のために /auth パス限定の必須Cookie（omaishort_rt、HttpOnly、SameSite=Lax）のみを使用します。広告や追跡用のCookieは使用しません。",
            ],
          },
          {
            code: "02",
            title: "ブラウザのlocalStorage設定",
            body: [
              "i18nextLng（表示言語: vi / en / ja）および omaishort.theme（サイトテーマ: brutal / soft）のみを保存します。",
            ],
          },
          {
            code: "03",
            title: "ホストChromeプロファイル（管理者専用）",
            body: [
              "管理者がChatGPT WebやGrok Imagineにログインした際のプロファイルは data/chatgpt-web/profile および data/grok-web/profile に保存され、一般ユーザー（creator）の画面には表示されません。",
            ],
          },
          {
            code: "04",
            title: "ローカルMP4ストレージ",
            body: [
              "生成されたMP4動画は data/jobs/<id>/render/short.mp4 に保存され、容量メタデータがCloudflare D1の storage_json に同期されます。",
            ],
          },
        ],
      },
    },
  },
};

const SEO_KEYS: Record<PolicySection, { titleKey: string; descriptionKey: string }> = {
  privacy: { titleKey: "meta.privacyTitle", descriptionKey: "meta.privacyDescription" },
  terms: { titleKey: "meta.termsTitle", descriptionKey: "meta.termsDescription" },
  cookies: { titleKey: "meta.cookiesTitle", descriptionKey: "meta.cookiesDescription" },
};

export function PolicyPage({ section }: { section: PolicySection }) {
  const { lang } = useParams<{ lang: string }>();
  const { t, i18n } = useTranslation();
  const activeLang: SupportedLang = SUPPORTED_LANGS.includes(lang as SupportedLang)
    ? (lang as SupportedLang)
    : "vi";

  useSEO({
    titleKey: SEO_KEYS[section].titleKey,
    descriptionKey: SEO_KEYS[section].descriptionKey,
    path: section,
    lang: activeLang,
  });

  useEffect(() => {
    if (activeLang !== i18n.language) {
      void i18n.changeLanguage(activeLang);
    }
    window.scrollTo({ top: 0 });
  }, [activeLang, section, i18n]);

  const copy = POLICY_COPY[activeLang];
  const current = copy.sections[section];

  return (
    <>
      <a className="skip-link" href="#main">
        {t("nav.skip")}
      </a>
      <Header />
      <main id="main" role="main" className="policy-main">
        <section className="section policy-hero">
          <div className="container">
            <div className="section-header">
              <span className="section-kicker">{copy.kicker}</span>
              <h1 className="section-title">{current.title}</h1>
              <p className="section-subtitle">{current.subtitle}</p>
              <p className="policy-updated">{copy.updated}</p>
            </div>

            <nav className="policy-tabs" aria-label={copy.kicker}>
              {(["privacy", "terms", "cookies"] as PolicySection[]).map((tabId) => (
                <Link
                  key={tabId}
                  to={`/${activeLang}/${tabId}`}
                  className={`policy-tab${section === tabId ? " active" : ""}`}
                  aria-current={section === tabId ? "page" : undefined}
                >
                  {copy.tabs[tabId]}
                </Link>
              ))}
            </nav>

            <div className="steps-grid policy-grid">
              {current.cards.map((card) => (
                <article key={card.code} className="step-card policy-card">
                  <div className="step-number">{card.code}</div>
                  <h2 className="step-title">{card.title}</h2>
                  {card.body.map((paragraph, idx) => (
                    <p key={idx} className="step-description">
                      {paragraph}
                    </p>
                  ))}
                </article>
              ))}
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}

