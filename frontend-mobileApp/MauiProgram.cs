using Microsoft.Extensions.Logging;
using SalesMobileApp.Services;
using SalesMobileApp.ViewModels;
using SalesMobileApp.Core;
namespace SalesMobileApp;
public static class MauiProgram
{
    public static MauiApp CreateMauiApp()
    {
        var builder = MauiApp.CreateBuilder();
        builder.UseMauiApp<App>().ConfigureFonts(fonts => { fonts.AddFont("OpenSans-Regular.ttf", "OpenSansRegular"); fonts.AddFont("OpenSans-Semibold.ttf", "OpenSansSemibold"); });
        builder.Services.AddSingleton(new HttpClient { Timeout = TimeSpan.FromSeconds(20) });
        builder.Services.AddSingleton<SessionStore>(); builder.Services.AddSingleton<ApiClient>();
        builder.Services.AddTransient<LoginViewModel>(); builder.Services.AddTransient<DashboardViewModel>(); builder.Services.AddTransient<HistoryViewModel>(); builder.Services.AddTransient<ProfileViewModel>();
#if DEBUG
        builder.Logging.AddDebug();
#endif
        var app = builder.Build(); ServiceLocator.Services = app.Services; return app;
    }
}
