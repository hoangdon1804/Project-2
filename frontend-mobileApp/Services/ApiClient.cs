using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using SalesMobileApp.Models;

namespace SalesMobileApp.Services;

public sealed class ApiClient
{
    private readonly HttpClient _http;
    private readonly SessionStore _session;
    private readonly JsonSerializerOptions _json = new(JsonSerializerDefaults.Web);
    private Uri? _baseUri;

    public ApiClient(HttpClient http, SessionStore session)
    {
        _http = http;
        _session = session;
    }

    public void SetBaseUrl(string url)
    {
        if (!Uri.TryCreate(url.Trim().TrimEnd('/') + "/", UriKind.Absolute, out var uri))
        {
            throw new InvalidOperationException("Backend URL khong hop le.");
        }

        _baseUri = uri;
    }

    private Uri BuildUri(string path)
    {
        return _baseUri is null
            ? throw new InvalidOperationException("Chua cau hinh Backend URL.")
            : new Uri(_baseUri, path);
    }

    private async Task<HttpRequestMessage> RequestAsync(HttpMethod method, string path)
    {
        var request = new HttpRequestMessage(method, BuildUri(path));
        var token = await _session.GetTokenAsync();

        if (!string.IsNullOrWhiteSpace(token))
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        }

        return request;
    }

    private async Task<T> SendAsync<T>(HttpRequestMessage request)
    {
        using var response = await _http.SendAsync(request);

        if (!response.IsSuccessStatusCode)
        {
            throw new ApiException(response.StatusCode, await response.Content.ReadAsStringAsync());
        }

        return (await response.Content.ReadFromJsonAsync<T>(_json))!;
    }

    public Task<LoginResponse> LoginAsync(string username, string password)
    {
        return SendAsync<LoginResponse>(
            new HttpRequestMessage(HttpMethod.Post, BuildUri("login"))
            {
                Content = JsonContent.Create(new LoginRequest(username, password), options: _json)
            });
    }

    public async Task<SalesProfile> GetProfileAsync(int id)
    {
        return await SendAsync<SalesProfile>(await RequestAsync(HttpMethod.Get, $"sales/{id}/profile"));
    }

    public async Task<SalesProfile> UpdateProfileAsync(int id, SalesProfile profile)
    {
        var request = await RequestAsync(HttpMethod.Put, $"sales/{id}/profile");
        request.Content = JsonContent.Create(
            new { email = profile.email, full_name = profile.full_name, phone = profile.phone },
            options: _json);

        return (await SendAsync<ProfileEnvelope>(request)).profile!;
    }

    public async Task<WorkShiftResponse> GetShiftAsync(int id)
    {
        return await SendAsync<WorkShiftResponse>(await RequestAsync(HttpMethod.Get, $"sales/{id}/work-shift"));
    }

    public async Task<List<SalesHistoryRow>> GetHistoryAsync(int id)
    {
        return await SendAsync<List<SalesHistoryRow>>(await RequestAsync(HttpMethod.Get, $"sales/{id}/sales-history"));
    }

    public async Task SubmitInvoiceAsync(int id, InvoiceRequest invoice)
    {
        var request = await RequestAsync(HttpMethod.Post, $"sales/{id}/invoices");
        request.Content = JsonContent.Create(invoice, options: _json);
        await SendAsync<JsonElement>(request);
    }
}

public sealed class ProfileEnvelope
{
    public SalesProfile? profile { get; set; }
}

public sealed class ApiException : Exception
{
    public HttpStatusCode StatusCode { get; }

    public ApiException(HttpStatusCode code, string detail)
        : base(string.IsNullOrWhiteSpace(detail) ? $"Backend tra ve {(int)code}." : detail)
    {
        StatusCode = code;
    }
}
